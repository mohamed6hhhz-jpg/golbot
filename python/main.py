"""
python/main.py

EWA Python Microservice — FastAPI HTTP Server
=============================================

Entry point for the Python EWA analysis service.
Next.js calls POST /analyze with just symbol + timeframes.
This service fetches its own OHLCV data from Bybit (fallback: OKX),
then runs the full 5-phase Elliott Wave pipeline and returns the
typed EWAResult JSON.

ARCHITECTURE CHANGE (v1.1):
  The service now fetches its own OHLCV data internally via Bybit/OKX.
  This permanently fixes the Binance 451 geo-restriction error that
  occurs when Next.js (on Render/Vercel) tries to call Binance from
  a cloud-server IP address.

  OLD: Next.js → Binance → bars → Python
  NEW: Next.js → Python → Bybit/OKX (no Binance, no IP restrictions)

SECURITY:
  - X-Service-Key header authentication (internal service-to-service)
  - Input validation via Pydantic models
  - Structured JSON errors (no stack traces in production)

DEPLOYMENT:
  Development:  uvicorn main:app --host 0.0.0.0 --port 8001 --reload
  Production:   gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker

ENVIRONMENT VARIABLES:
  EWA_SERVICE_KEY : Shared secret between Next.js and this service
  EWA_LOG_LEVEL   : DEBUG | INFO | WARNING  (default: INFO)
  EWA_ATR_MULT    : ATR multiplier for pivot detection (default: 2.5)
  EWA_MACRO_LIMIT : Bars to fetch for macro TF (default: 500)
  EWA_MICRO_LIMIT : Bars to fetch for micro TF (default: 300)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ewa.orchestrator import EWAOrchestrator
from ewa.market_fetcher import fetch_dual_tf

# ─── Logging Setup ────────────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("EWA_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ewa.server")

# ─── Configuration ────────────────────────────────────────────────────────────

SERVICE_KEY  = os.getenv("EWA_SERVICE_KEY", "dev-internal-key")
ATR_MULT     = float(os.getenv("EWA_ATR_MULT",    "2.5"))
MACRO_LIMIT  = int(os.getenv("EWA_MACRO_LIMIT",   "500"))
MICRO_LIMIT  = int(os.getenv("EWA_MICRO_LIMIT",   "300"))

# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="EWA Python Microservice",
    description=(
        "Elliott Wave Quantitative Analysis Engine. "
        "Data is sourced from Bybit (fallback: OKX) — no Binance dependency."
    ),
    version="1.1.0",
    docs_url="/docs" if os.getenv("NODE_ENV") != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_methods=["POST"],
    allow_headers=["Content-Type", "X-Service-Key"],
)

# Single shared orchestrator instance (stateless — safe to share across workers)
orchestrator = EWAOrchestrator()

# ─── Pydantic Models ──────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """
    Lean request payload from Next.js /api/ewa route handler.
    The Python service now fetches its own OHLCV bars internally via Bybit/OKX.
    No OHLCV data is passed from Next.js — only the symbol and timeframes.
    """
    symbol:           str = Field(..., min_length=2, max_length=20,
                                  description="Trading pair e.g. 'BTCUSDT'")
    macro_tf:         str = Field(..., pattern=r"^(15m|1h|4h|1d|3d|1w)$",
                                  description="Higher timeframe e.g. '1d'")
    micro_tf:         str = Field(..., pattern=r"^(15m|1h|4h|1d|3d|1w)$",
                                  description="Lower timeframe e.g. '1h'")
    telegram_user_id: int = Field(..., gt=0,
                                  description="Verified Telegram user ID (from Next.js auth)")

    class Config:
        extra = "forbid"  # Reject unexpected fields


class HealthResponse(BaseModel):
    status:     str
    version:    str
    uptime:     float
    data_source: str


# ─── Auth Dependency ──────────────────────────────────────────────────────────

async def verify_service_key(request: Request) -> None:
    """
    Verify the X-Service-Key header matches the shared secret.
    Internal service-to-service auth — NOT end-user auth.
    End-user auth (Telegram initData) is verified in Next.js before calling this.
    """
    key = request.headers.get("X-Service-Key", "")
    if key != SERVICE_KEY:
        log.warning(
            f"[Auth] Invalid service key from "
            f"{request.client.host if request.client else 'unknown'}."
        )
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid service key.", "code": "UNAUTHORIZED"},
        )


# ─── Routes ───────────────────────────────────────────────────────────────────

_start_time = time.time()


@app.get("/health", response_model=HealthResponse, tags=["monitoring"])
async def health() -> dict:
    """Health check endpoint — used by Docker/Render liveness probe."""
    return {
        "status":      "ok",
        "version":     "1.1.0",
        "uptime":      round(time.time() - _start_time, 1),
        "data_source": "Bybit (fallback: OKX)",
    }


@app.post("/analyze", tags=["analysis"], dependencies=[Depends(verify_service_key)])
async def analyze(request_body: AnalyzeRequest) -> JSONResponse:
    """
    Full Elliott Wave analysis endpoint.

    1. Fetches OHLCV bars from Bybit Spot API (OKX fallback).
    2. Runs the 5-phase EWA pipeline on the fetched data.
    3. Returns the typed EWAResult JSON.

    Called exclusively by Next.js app/api/ewa/route.ts — not a public endpoint.
    Data is sourced from Bybit/OKX — no Binance dependency.
    """
    request_start = time.time()
    sym = request_body.symbol.upper()

    log.info(
        f"[/analyze] {sym} {request_body.macro_tf}→{request_body.micro_tf} "
        f"user={request_body.telegram_user_id}"
    )

    # ── Step 1: Fetch OHLCV data from Bybit/OKX ──────────────────────────────
    try:
        macro_bars, micro_bars = fetch_dual_tf(
            symbol=sym,
            macro_tf=request_body.macro_tf,
            micro_tf=request_body.micro_tf,
            macro_limit=MACRO_LIMIT,
            micro_limit=MICRO_LIMIT,
        )
    except Exception as e:
        log.error(f"[/analyze] Data fetch failed for {sym}: {e}")
        return JSONResponse(
            status_code=502,
            content={
                "error":  f"Market data unavailable: {e}",
                "code":   "DATA_FETCH_ERROR",
                "symbol": sym,
                "detail": (
                    "Both Bybit and OKX failed to return data for this symbol. "
                    "Check that the symbol is a valid Spot pair (e.g. BTCUSDT)."
                ),
            },
        )

    fetch_elapsed = round((time.time() - request_start) * 1000)
    log.info(
        f"[/analyze] Data ready: macro={len(macro_bars)} micro={len(micro_bars)} "
        f"bars in {fetch_elapsed}ms"
    )

    # ── Step 2: Run 5-phase EWA pipeline ─────────────────────────────────────
    try:
        result = orchestrator.analyze(
            symbol=sym,
            macro_tf=request_body.macro_tf,
            micro_tf=request_body.micro_tf,
            macro_bars=macro_bars,
            micro_bars=micro_bars,
            atr_multiplier=ATR_MULT,
        )
    except Exception as e:
        log.exception(f"[/analyze] Pipeline error for {sym}: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error":  "Internal analysis error. The wave engine encountered an unexpected state.",
                "code":   "ANALYSIS_ERROR",
                "symbol": sym,
                **({"detail": str(e)} if os.getenv("NODE_ENV") != "production" else {}),
            },
        )

    # ── Step 3: Respond ───────────────────────────────────────────────────────
    total_elapsed = round((time.time() - request_start) * 1000)
    log.info(
        f"[/analyze] ✓ {sym} "
        f"confidence={result.get('scoring_matrix', {}).get('confidence_pct', 0)}% "
        f"total={total_elapsed}ms (fetch={fetch_elapsed}ms)"
    )

    if "_pivot_debug" in result:
        result["_pivot_debug"]["server_elapsed_ms"]  = total_elapsed
        result["_pivot_debug"]["fetch_elapsed_ms"]   = fetch_elapsed
        result["_pivot_debug"]["macro_bars_fetched"]  = len(macro_bars)
        result["_pivot_debug"]["micro_bars_fetched"]  = len(micro_bars)
        result["_pivot_debug"]["data_source"]         = "Bybit/OKX"

    return JSONResponse(content=result)


# ─── Global Exception Handlers ────────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail if isinstance(exc.detail, dict)
                else {"error": exc.detail, "code": "HTTP_ERROR"},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception(f"[GlobalHandler] Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error.", "code": "INTERNAL_ERROR"},
    )


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("EWA_PORT", "8001")),
        reload=os.getenv("NODE_ENV") != "production",
        log_level=LOG_LEVEL.lower(),
    )
