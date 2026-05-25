"""
ewa/market_fetcher.py

OHLCV Data Fetcher — Bybit (Primary) + OKX (Fallback)
======================================================

Replaces all Binance API calls. Bybit and OKX do NOT block cloud
server IPs (Render, Railway, Fly.io, DigitalOcean, etc.).

EXCHANGE PRIORITY:
  1. Bybit Spot V5 API  → https://api.bybit.com/v5/market/kline
  2. OKX Spot API       → https://www.okx.com/api/v5/market/candles
     (fallback if Bybit fails for any reason)

OUTPUT FORMAT:
  Each bar is returned as a dict matching OHLCVBar.from_dict():
    {
      "t":         int,    # Open timestamp (Unix seconds)
      "o":         float,  # Open price
      "h":         float,  # High price
      "l":         float,  # Low price
      "c":         float,  # Close price
      "v":         float,  # Volume (base asset)
      "tc":        int,    # Close timestamp (Unix seconds) — approximated
      "is_closed": bool,   # Always True for historical bars
    }
  Bars are returned oldest-first (ascending timestamp), matching what
  the pivot engine expects.

SYMBOL NORMALISATION:
  Input symbol is always the Binance-style "BTCUSDT".
  Bybit accepts "BTCUSDT" directly for spot.
  OKX requires "BTC-USDT" (dash-separated).

TIMEFRAME MAPPING:
  Internal TF  │ Bybit Interval │ OKX Bar
  ─────────────┼────────────────┼────────
  15m          │ 15             │ 15m
  1h           │ 60             │ 1H
  4h           │ 240            │ 4H
  1d           │ D              │ 1D
  3d           │ D              │ 3D   (3D not on Bybit — fetch 3× 1D)
  1w           │ W              │ 1W
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

BYBIT_BASE  = "https://api.bybit.com"
OKX_BASE    = "https://www.okx.com"

REQUEST_TIMEOUT = 15.0  # seconds

# Bybit interval codes for Spot V5 API
BYBIT_TF_MAP: dict[str, str] = {
    "15m": "15",
    "1h":  "60",
    "4h":  "240",
    "1d":  "D",
    "3d":  "D",   # Bybit has no 3D — fetch D and let caller decide bar count
    "1w":  "W",
}

# OKX bar codes
OKX_TF_MAP: dict[str, str] = {
    "15m": "15m",
    "1h":  "1H",
    "4h":  "4H",
    "1d":  "1D",
    "3d":  "3D",
    "1w":  "1W",
}

# OKX max limit per request (hard limit is 300)
OKX_MAX_LIMIT = 300
# Bybit max limit per request (hard limit is 1000)
BYBIT_MAX_LIMIT = 1000


# ─── Bybit Fetcher ────────────────────────────────────────────────────────────

def _bybit_symbol(symbol: str) -> str:
    """Bybit Spot accepts the same format as Binance: 'BTCUSDT'."""
    return symbol.upper().replace("-", "").replace("/", "")


def _fetch_bybit(symbol: str, timeframe: str, limit: int) -> list[dict]:
    """
    Fetch OHLCV bars from Bybit Spot V5 API.
    Returns bars in ascending order (oldest first).

    Bybit response format (each element):
      [startTime_ms, open, high, low, close, volume, turnover]
    Bybit returns newest-first — we reverse before returning.
    """
    interval = BYBIT_TF_MAP.get(timeframe)
    if not interval:
        raise ValueError(f"[Bybit] Unsupported timeframe: {timeframe}")

    actual_limit = min(limit, BYBIT_MAX_LIMIT)
    sym = _bybit_symbol(symbol)

    url = f"{BYBIT_BASE}/v5/market/kline"
    params = {
        "category": "spot",
        "symbol":   sym,
        "interval": interval,
        "limit":    actual_limit,
    }

    log.info(f"[Bybit] Fetching {sym} {interval} limit={actual_limit}")
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        resp = client.get(url, params=params)

    resp.raise_for_status()
    data = resp.json()

    ret_code = data.get("retCode", -1)
    if ret_code != 0:
        raise RuntimeError(
            f"[Bybit] API error retCode={ret_code} msg={data.get('retMsg', '')}"
        )

    raw_list: list[list] = data.get("result", {}).get("list", [])
    if not raw_list:
        raise RuntimeError(f"[Bybit] Empty response for {sym} {interval}")

    # Bybit returns newest-first → reverse to get oldest-first
    raw_list = list(reversed(raw_list))

    bars = []
    for row in raw_list:
        # [startTime_ms, open, high, low, close, volume, turnover]
        t_ms = int(row[0])
        t_s  = t_ms // 1000
        bars.append({
            "t":         t_s,
            "o":         float(row[1]),
            "h":         float(row[2]),
            "l":         float(row[3]),
            "c":         float(row[4]),
            "v":         float(row[5]),
            "tc":        t_s,        # Bybit doesn't send explicit close time
            "is_closed": True,
        })

    log.info(f"[Bybit] ✓ {sym} {interval}: {len(bars)} bars returned")
    return bars


# ─── OKX Fallback Fetcher ─────────────────────────────────────────────────────

def _okx_symbol(symbol: str) -> str:
    """
    Convert 'BTCUSDT' → 'BTC-USDT' for OKX.
    OKX uses '-' separated instId format.
    """
    s = symbol.upper().replace("-", "").replace("/", "")
    # Strip common quote currencies and reattach with dash
    for quote in ("USDT", "USDC", "BTC", "ETH", "BNB"):
        if s.endswith(quote) and len(s) > len(quote):
            base = s[: len(s) - len(quote)]
            return f"{base}-{quote}"
    return s


def _fetch_okx(symbol: str, timeframe: str, limit: int) -> list[dict]:
    """
    Fetch OHLCV bars from OKX Spot API as a fallback.
    OKX hard-limits to 300 bars per request.
    Returns bars in ascending order (oldest first).

    OKX response format (each element):
      [timestamp_ms, open, high, low, close, vol, volCcy, volCcyQuote, confirm]
    OKX returns newest-first — we reverse before returning.
    """
    bar = OKX_TF_MAP.get(timeframe)
    if not bar:
        raise ValueError(f"[OKX] Unsupported timeframe: {timeframe}")

    actual_limit = min(limit, OKX_MAX_LIMIT)
    inst_id = _okx_symbol(symbol)

    url = f"{OKX_BASE}/api/v5/market/candles"
    params = {
        "instId": inst_id,
        "bar":    bar,
        "limit":  actual_limit,
    }

    log.info(f"[OKX] Fetching {inst_id} {bar} limit={actual_limit}")
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        resp = client.get(url, params=params)

    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != "0":
        raise RuntimeError(
            f"[OKX] API error code={data.get('code')} msg={data.get('msg', '')}"
        )

    raw_list: list[list] = data.get("data", [])
    if not raw_list:
        raise RuntimeError(f"[OKX] Empty response for {inst_id} {bar}")

    # OKX returns newest-first → reverse to get oldest-first
    raw_list = list(reversed(raw_list))

    bars = []
    for row in raw_list:
        # [ts_ms, open, high, low, close, vol, volCcy, volCcyQuote, confirm]
        t_ms = int(row[0])
        t_s  = t_ms // 1000
        bars.append({
            "t":         t_s,
            "o":         float(row[1]),
            "h":         float(row[2]),
            "l":         float(row[3]),
            "c":         float(row[4]),
            "v":         float(row[5]),
            "tc":        t_s,
            "is_closed": True,
        })

    log.info(f"[OKX] ✓ {inst_id} {bar}: {len(bars)} bars returned")
    return bars


# ─── Public Interface ─────────────────────────────────────────────────────────

def fetch_ohlcv(symbol: str, timeframe: str, limit: int) -> list[dict]:
    """
    Fetch OHLCV bars with automatic fallback.

    Tries Bybit first. If Bybit fails for any reason (network error,
    non-200 response, empty data), falls back to OKX automatically.

    Parameters
    ----------
    symbol    : Trading pair in Binance format e.g. "BTCUSDT"
    timeframe : One of: "15m", "1h", "4h", "1d", "3d", "1w"
    limit     : Number of bars to fetch (capped by exchange limits internally)

    Returns
    -------
    list of OHLCV dicts in ascending order (oldest first), matching OHLCVBar.from_dict()
    """
    # ── Try Bybit first ───────────────────────────────────────────────────────
    try:
        bars = _fetch_bybit(symbol, timeframe, limit)
        if len(bars) >= 10:
            return bars
        log.warning(f"[Bybit] Only {len(bars)} bars for {symbol} {timeframe}, trying OKX")
    except Exception as e:
        log.warning(f"[Bybit] Failed for {symbol} {timeframe}: {e}. Falling back to OKX.")

    # ── Fallback to OKX ───────────────────────────────────────────────────────
    try:
        bars = _fetch_okx(symbol, timeframe, limit)
        if len(bars) >= 10:
            return bars
        raise RuntimeError(f"OKX returned only {len(bars)} bars (need ≥ 10)")
    except Exception as e:
        log.error(f"[OKX] Also failed for {symbol} {timeframe}: {e}")
        raise RuntimeError(
            f"All data sources failed for {symbol} {timeframe}. "
            f"Last error: {e}"
        ) from e


def fetch_dual_tf(
    symbol:      str,
    macro_tf:    str,
    micro_tf:    str,
    macro_limit: int = 500,
    micro_limit: int = 300,
) -> tuple[list[dict], list[dict]]:
    """
    Fetch OHLCV bars for two timeframes concurrently using threads.

    Returns
    -------
    (macro_bars, micro_bars) — each a list of OHLCV dicts, oldest first
    """
    import concurrent.futures

    log.info(
        f"[MarketFetcher] Fetching {symbol}: "
        f"macro={macro_tf}×{macro_limit} micro={micro_tf}×{micro_limit}"
    )
    t0 = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        macro_fut = pool.submit(fetch_ohlcv, symbol, macro_tf, macro_limit)
        micro_fut = pool.submit(fetch_ohlcv, symbol, micro_tf, micro_limit)
        macro_bars = macro_fut.result()
        micro_bars = micro_fut.result()

    elapsed = round((time.time() - t0) * 1000)
    log.info(
        f"[MarketFetcher] ✓ {symbol}: "
        f"macro={len(macro_bars)} micro={len(micro_bars)} bars in {elapsed}ms"
    )
    return macro_bars, micro_bars
