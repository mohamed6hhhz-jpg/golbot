"""
ewa/orchestrator.py

The EWA Engine Orchestrator — Assembles the Full EWAResult JSON
===============================================================

This is the single entry point for the Python microservice.
It receives raw OHLCV bars, runs all 5 engine phases in order,
and returns the complete typed EWAResult JSON that Next.js renders.

PIPELINE:
  Phase 2: detect_pivots()              → PivotEngineResult (macro + micro)
  Phase 2: extract_wave_candidates()    → candidate pivot windows
  Phase 3: ElliottGuard.validate_all()  → valid ElliottGuardResults
  Phase 4: MTFStateMachine.resolve()    → MTFResult (contradiction resolution)
  Phase 5: TargetEngine.compute()       → TargetResult (SL + TP)
  Phase 6: _build_json()                → Final EWAResult dict

ARABIC PATTERN NAMES (from UI images):
  Bullish Impulse      → "موجة دافعة صاعدة — 1-2-3-4-5"
  Bearish Impulse      → "موجة دافعة هابطة — 1-2-3-4-5"
  Bullish Zigzag       → "تصحيح صاعد متعرج — A-B-C"
  Bearish Zigzag       → "تصحيح هابط متعرج — A-B-C"
  Bullish Flat         → "تصحيح مسطح صاعد — A-B-C"
  Bearish Flat         → "تصحيح مسطح هابط — A-B-C"
  Ending Diagonal      → "مثلث قُطري نهائي"
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .pivot_engine import (
    OHLCVBar,
    detect_pivots,
    extract_wave_candidates,
)
from .elliott_guard import ElliottGuard, ElliottGuardResult
from .mtf_state_machine import MTFStateMachine, MTFAlignment
from .target_engine import TargetEngine

log = logging.getLogger(__name__)


# ─── Pattern Display Names ────────────────────────────────────────────────────

PATTERN_NAMES: dict[str, dict[str, str]] = {
    "impulse_bullish": {
        "en": "BULLISH IMPULSE",
        "ar": "موجة دافعة صاعدة — 1-2-3-4-5",
        "label": "1-2-3-4-5",
    },
    "impulse_bearish": {
        "en": "BEARISH IMPULSE",
        "ar": "موجة دافعة هابطة — 1-2-3-4-5",
        "label": "1-2-3-4-5",
    },
    "zigzag_bullish": {
        "en": "BULLISH ZIGZAG",
        "ar": "تصحيح صاعد متعرج — A-B-C",
        "label": "A-B-C",
    },
    "zigzag_bearish": {
        "en": "BEARISH ZIGZAG",
        "ar": "تصحيح هابط متعرج — A-B-C",
        "label": "A-B-C",
    },
    "corrective_abc_bullish": {
        "en": "BULLISH CORRECTION",
        "ar": "تصحيح صاعد — A-B-C",
        "label": "A-B-C",
    },
    "corrective_abc_bearish": {
        "en": "BEARISH CORRECTION",
        "ar": "تصحيح هابط — A-B-C",
        "label": "A-B-C",
    },
    "flat_bullish": {
        "en": "BULLISH FLAT",
        "ar": "تصحيح مسطح صاعد — A-B-C",
        "label": "A-B-C",
    },
    "flat_bearish": {
        "en": "BEARISH FLAT",
        "ar": "تصحيح مسطح هابط — A-B-C",
        "label": "A-B-C",
    },
    "diagonal_ending_bullish": {
        "en": "BULLISH ENDING DIAGONAL",
        "ar": "مثلث قُطري نهائي صاعد",
        "label": "1-2-3-4-5",
    },
    "diagonal_ending_bearish": {
        "en": "BEARISH ENDING DIAGONAL",
        "ar": "مثلث قُطري نهائي هابط",
        "label": "1-2-3-4-5",
    },
}

PIVOT_WAVE_LABELS_IMPULSE    = ["0", "1", "2", "3", "4", "5"]
PIVOT_WAVE_LABELS_CORRECTIVE = ["0", "A", "B", "C"]


# ─── Confidence Score Computation ────────────────────────────────────────────

def _compute_confidence(
    rules_score:     int,   # 0 or 40
    structure_score: int,   # 0–20
    fib_score:       int,   # 0–25
    mtf_score:       int,   # 0–10
    momentum_score:  int,   # 0–5
) -> int:
    """
    Final confidence score out of 100.
    Weights match the Scoring Matrix shown in the UI images:
        Elliott Rules  : 40%
        Fibonacci      : 25%
        Structure      : 20%
        MTF Alignment  : 10%
        Macro Momentum : 5%
    """
    total = rules_score + fib_score + structure_score + mtf_score + momentum_score
    return min(100, max(0, total))


# ─── Algorithmic Verdict Builder ──────────────────────────────────────────────

def _build_verdict(
    pattern_name_en: str,
    confidence:      int,
    guard_result:    ElliottGuardResult,
    mtf_description_ar: str,
    invalidation_label: str,
    is_bearish:      bool,
) -> tuple[str, str]:
    """
    Build the Arabic and English algorithmic verdict strings shown at the
    bottom of the UI card (matches the text in image_4 and image_5).
    """
    rules_ok = "جميع القواعد الإلزامية محققة رياضياً" \
               if guard_result.rules_score > 0 \
               else "تحذير: بعض القواعد الإلزامية غير مُحققة"

    w3_check = ""
    for g in guard_result.guidelines:
        if g.guideline_id == "G1":
            w3_check = "الموجة 3 ليست الأقصر." if g.passed else "تحذير: الموجة 3 قد تكون الأقصر."
            break

    verdict_ar = (
        f"محرك إليوت الكمي استخرج سيناريو {pattern_name_en} بدرجة {confidence}%. "
        f"{rules_ok}. {w3_check} "
        f"التراتيب متوافق مع الفريم الأكبر ({'BEARISH' if is_bearish else 'BULLISH'}). "
        f"تحذير استثماري: يُلغى السيناريو كلياً وتعتبر خاطئاً في حال تجاوز "
        f"مستوى الإلغاء الصارم عند {invalidation_label}"
    )

    verdict_en = (
        f"Quant Elliott engine identified {pattern_name_en} at {confidence}% confidence. "
        f"{rules_ok.replace('جميع القواعد الإلزامية محققة رياضياً', 'All 3 inviolable rules pass mathematically.')} "
        f"MTF context: {mtf_description_ar[:80]}. "
        f"STRICT STOP: {invalidation_label} — any close beyond this level invalidates entirely."
    )

    return verdict_ar, verdict_en


# ─── Orchestrator ─────────────────────────────────────────────────────────────

class EWAOrchestrator:
    """
    Main orchestrator for the Elliott Wave Analysis engine.
    Call analyze() with dual-timeframe OHLCV arrays to get the full EWAResult.
    """

    def __init__(self) -> None:
        self.guard   = ElliottGuard()
        self.mtf     = MTFStateMachine()
        self.targets = TargetEngine()

    def analyze(
        self,
        symbol:          str,
        macro_tf:        str,
        micro_tf:        str,
        macro_bars:      list[dict],
        micro_bars:      list[dict],
        atr_multiplier:  float = 2.5,
        max_pivot_count: int   = 60,
    ) -> dict[str, Any]:
        """
        Full analysis pipeline. Returns EWAResult dict ready for JSON serialization.

        Parameters
        ----------
        symbol         : Trading pair e.g. "BTCUSDT"
        macro_tf       : Higher timeframe e.g. "1d"
        micro_tf       : Lower timeframe e.g. "1h"
        macro_bars     : OHLCV bars for macro TF (list of dicts matching OHLCVBar.from_dict)
        micro_bars     : OHLCV bars for micro TF
        atr_multiplier : Pivot detection sensitivity (higher = fewer, more significant pivots)
        max_pivot_count: Max pivots to detect per timeframe
        """
        start_ts = time.time()
        symbol_clean = symbol.upper().replace("USDT", "").strip()  # "BTC" from "BTCUSDT"

        log.info(f"[EWAOrchestrator] Starting analysis: {symbol} {macro_tf}→{micro_tf} "
                 f"macro={len(macro_bars)} bars micro={len(micro_bars)} bars")

        # ── Phase 2: Convert and detect pivots ──────────────────────────────
        try:
            macro_ohlcv = [OHLCVBar.from_dict(b) for b in macro_bars]
            micro_ohlcv = [OHLCVBar.from_dict(b) for b in micro_bars]
        except (KeyError, TypeError, ValueError) as e:
            return self._error_result(symbol_clean, macro_tf, micro_tf,
                                      f"Bar parsing error: {e}")

        try:
            macro_pivots_result = detect_pivots(
                macro_ohlcv, symbol=symbol, timeframe=macro_tf,
                atr_multiplier=atr_multiplier, max_pivots=max_pivot_count,
            )
            micro_pivots_result = detect_pivots(
                micro_ohlcv, symbol=symbol, timeframe=micro_tf,
                atr_multiplier=atr_multiplier, max_pivots=max_pivot_count,
            )
        except ValueError as e:
            return self._error_result(symbol_clean, macro_tf, micro_tf, str(e))

        if macro_pivots_result.pivot_count < 4:
            return self._error_result(
                symbol_clean, macro_tf, micro_tf,
                f"Insufficient macro pivots: {macro_pivots_result.pivot_count} detected, "
                f"minimum 4 required for Elliott Wave analysis. "
                f"Try increasing bar count or reducing atr_multiplier.",
                insufficient_pivots=True,
            )

        if micro_pivots_result.pivot_count < 4:
            return self._error_result(
                symbol_clean, macro_tf, micro_tf,
                f"Insufficient micro pivots: {micro_pivots_result.pivot_count} detected.",
                insufficient_pivots=True,
            )

        # ── Phase 2b: Extract candidate windows ─────────────────────────────
        macro_impulse_candidates    = extract_wave_candidates(macro_pivots_result.pivots, window=6)
        macro_corrective_candidates = extract_wave_candidates(macro_pivots_result.pivots, window=4)
        micro_impulse_candidates    = extract_wave_candidates(micro_pivots_result.pivots, window=6)
        micro_corrective_candidates = extract_wave_candidates(micro_pivots_result.pivots, window=4)

        log.debug(
            f"Candidates — macro: {len(macro_impulse_candidates)} impulse, "
            f"{len(macro_corrective_candidates)} corrective | "
            f"micro: {len(micro_impulse_candidates)} impulse, "
            f"{len(micro_corrective_candidates)} corrective"
        )

        # ── Phase 3: Elliott Guard validation ───────────────────────────────
        valid_macro = self.guard.validate_all_candidates(
            macro_impulse_candidates, macro_corrective_candidates, max_results=5
        )
        valid_micro = self.guard.validate_all_candidates(
            micro_impulse_candidates, micro_corrective_candidates, max_results=8
        )

        log.info(
            f"[EWAOrchestrator] Guard results — "
            f"macro: {len(valid_macro)} valid / micro: {len(valid_micro)} valid"
        )

        # ── Phase 4: MTF State Machine ───────────────────────────────────────
        latest_micro_close = micro_ohlcv[-1].c if micro_ohlcv else 0.0
        mtf_result = self.mtf.resolve(
            macro_candidates=valid_macro,
            micro_candidates=valid_micro,
            macro_tf=macro_tf,
            micro_tf=micro_tf,
            latest_micro_close=latest_micro_close,
        )

        # Select the primary result for target computation
        # Prefer the MTF-aligned micro result; fallback to best macro
        primary_result: ElliottGuardResult | None = mtf_result.micro_result
        if primary_result is None:
            # Contradiction: use best macro result as primary
            primary_result = max(valid_macro, key=lambda r: r.base_score) \
                             if valid_macro else None

        if primary_result is None:
            return self._error_result(
                symbol_clean, macro_tf, micro_tf,
                "No valid Elliott Wave count found on either timeframe.",
            )

        # ── Phase 5: Target computation ──────────────────────────────────────
        current_price = latest_micro_close
        target_result = self.targets.compute(primary_result, current_price)

        # ── Phase 6: Build final JSON ────────────────────────────────────────
        analysis_ts = int(time.time())
        elapsed_ms  = round((time.time() - start_ts) * 1000)

        result = self._build_json(
            symbol=symbol_clean,
            macro_tf=macro_tf,
            micro_tf=micro_tf,
            analysis_ts=analysis_ts,
            current_price=current_price,
            primary_result=primary_result,
            mtf_result=mtf_result,
            target_result=target_result,
            macro_pivots_result=macro_pivots_result,
            micro_pivots_result=micro_pivots_result,
            elapsed_ms=elapsed_ms,
        )

        log.info(
            f"[EWAOrchestrator] Complete: {symbol} confidence={result['scoring_matrix']['confidence_pct']}% "
            f"pattern={result['pattern_name_en']} elapsed={elapsed_ms}ms"
        )

        return result

    # ─── JSON Builder ──────────────────────────────────────────────────────

    def _build_json(
        self,
        symbol:              str,
        macro_tf:            str,
        micro_tf:            str,
        analysis_ts:         int,
        current_price:       float,
        primary_result:      ElliottGuardResult,
        mtf_result:          "MTFResult",
        target_result:       "TargetResult",
        macro_pivots_result: "PivotEngineResult",
        micro_pivots_result: "PivotEngineResult",
        elapsed_ms:          int,
    ) -> dict[str, Any]:
        """
        Assemble the final EWAResult JSON schema.
        All fields match the TypeScript EWAResult interface exactly.
        """
        direction  = primary_result.direction
        ptype      = primary_result.pattern_type
        is_bearish = direction == "bearish"

        # Pattern display names
        pattern_key = f"{ptype}_{direction}"
        names = PATTERN_NAMES.get(pattern_key, {
            "en": ptype.upper().replace("_", " "),
            "ar": ptype,
            "label": "?",
        })

        # Wave pivot labels for SVG rendering
        is_corrective = ptype in ("corrective_abc", "zigzag", "flat", "triangle")
        wave_labels   = PIVOT_WAVE_LABELS_CORRECTIVE if is_corrective \
                        else PIVOT_WAVE_LABELS_IMPULSE

        # Build pivot objects for Next.js SVG rendering
        pivots_json = []
        for i, p in enumerate(primary_result.pivots):
            label = wave_labels[i] if i < len(wave_labels) else str(i)
            pivots_json.append({
                "label":      label,
                "timestamp":  p.timestamp,
                "price":      round(p.price, 8),
                "pivot_type": p.pivot_type,
                "bar_index":  p.bar_index,
                "prominence": round(p.prominence, 4),
            })

        # Scoring matrix
        confidence = _compute_confidence(
            rules_score=primary_result.rules_score,
            structure_score=primary_result.structure_score,
            fib_score=primary_result.fib_score,
            mtf_score=mtf_result.mtf_score,
            momentum_score=mtf_result.momentum_score,
        )

        scoring_matrix = {
            "total_score":     confidence,
            "confidence_pct":  confidence,
            "macro_momentum": {
                "score":      mtf_result.momentum_score,
                "max":        5,
                "weight_pct": 5,
            },
            "mtf_alignment": {
                "score":      mtf_result.mtf_score,
                "max":        10,
                "weight_pct": 10,
            },
            "structure": {
                "score":      primary_result.structure_score,
                "max":        20,
                "weight_pct": 20,
            },
            "fibonacci": {
                "score":      primary_result.fib_score,
                "max":        25,
                "weight_pct": 25,
            },
            "elliott_rules": {
                "score":      primary_result.rules_score,
                "max":        40,
                "weight_pct": 40,
            },
        }

        # MTF alignment block
        mtf_json = {
            "macro_timeframe":      macro_tf,
            "micro_timeframe":      micro_tf,
            "macro_state":          mtf_result.macro_position.value,
            "macro_direction":      mtf_result.macro_direction,
            "mtf_aligned":          mtf_result.alignment != MTFAlignment.CONTRADICTION,
            "mtf_score":            mtf_result.mtf_score,
            "alignment":            mtf_result.alignment.value,
            "bias_description_ar":  mtf_result.description_ar,
            "bias_description_en":  mtf_result.description_en,
        }
        if mtf_result.contradiction_reason:
            mtf_json["contradiction_reason"] = mtf_result.contradiction_reason

        # Fibonacci relations
        fib_json = {
            "fib_score":     primary_result.fib_score,
            "max_fib_score": 25,
            "relations": [
                {
                    "waves":          g.guideline_id,
                    "name":           g.guideline_name,
                    "actual_ratio":   round(g.ratio, 4),
                    "near_level":     round(g.ideal_ratio, 4),
                    "deviation_pct":  round(g.deviation_pct, 2),
                    "passes":         g.passed,
                    "score":          round(g.score, 3),
                }
                for g in primary_result.guidelines
            ],
        }

        # Elliott rules block
        rules_json = {
            "all_pass":   primary_result.rules_score > 0,
            "rules_score": primary_result.rules_score,
            "is_diagonal": primary_result.is_diagonal,
            "rules": [
                {
                    "id":          r.rule_id,
                    "name":        r.rule_name,
                    "passed":      r.passed,
                    "detail":      r.detail,
                    "is_critical": r.is_critical,
                }
                for r in primary_result.rules
            ],
            "guidelines": [
                {
                    "id":          g.guideline_id,
                    "name":        g.guideline_name,
                    "passed":      g.passed,
                    "ratio":       round(g.ratio, 4),
                    "ideal_ratio": round(g.ideal_ratio, 4),
                }
                for g in primary_result.guidelines
            ],
        }

        # Verdicts
        verdict_ar, verdict_en = _build_verdict(
            pattern_name_en=names["en"],
            confidence=confidence,
            guard_result=primary_result,
            mtf_description_ar=mtf_result.description_ar,
            invalidation_label=target_result.invalidation_label,
            is_bearish=is_bearish,
        )

        # Meta strip (bottom row of UI card)
        fmt_price_simple = f"${current_price:,.2f}" if current_price >= 1 \
                           else f"${current_price:.5f}"
        meta = {
            "inv":     target_result.invalidation_label,
            "dir":     "DN" if is_bearish else "UP",
            "pattern": names["label"],
            "price":   fmt_price_simple,
            "pair":    symbol,
        }

        # Pivot engine debug info (useful for UI debugging, not shown to users)
        pivot_debug = {
            "macro_pivot_count":     macro_pivots_result.pivot_count,
            "micro_pivot_count":     micro_pivots_result.pivot_count,
            "macro_atr":             round(macro_pivots_result.atr, 8),
            "micro_atr":             round(micro_pivots_result.atr, 8),
            "macro_prominence_used": round(macro_pivots_result.prominence_used, 8),
            "micro_prominence_used": round(micro_pivots_result.prominence_used, 8),
            "analysis_elapsed_ms":   elapsed_ms,
        }

        return {
            # ── Identity ──────────────────────────────────────────────────
            "symbol":          symbol,
            "macro_timeframe": macro_tf,
            "micro_timeframe": micro_tf,
            "analysis_ts":     analysis_ts,
            "current_price":   round(current_price, 8),

            # ── Pattern Classification ─────────────────────────────────────
            "pattern_type":    ptype,
            "pattern_label":   names["label"],
            "direction":       direction,
            "pattern_name_en": names["en"],
            "pattern_name_ar": names["ar"],

            # ── Wave Pivots (SVG rendering coordinates) ───────────────────
            "pivots":          pivots_json,

            # ── Validation Blocks ──────────────────────────────────────────
            "elliott_rules":   rules_json,
            "fibonacci":       fib_json,
            "mtf_alignment":   mtf_json,

            # ── Scoring ────────────────────────────────────────────────────
            "scoring_matrix":  scoring_matrix,

            # ── Trade Levels ───────────────────────────────────────────────
            "targets":         target_result.to_dict(),

            # ── UI Meta Strip ──────────────────────────────────────────────
            "meta":            meta,

            # ── Algorithmic Verdict ────────────────────────────────────────
            "verdict_ar":      verdict_ar,
            "verdict_en":      verdict_en,

            # ── Debug / Transparency ──────────────────────────────────────
            "_pivot_debug":    pivot_debug,
        }

    # ─── Error Result ──────────────────────────────────────────────────────

    def _error_result(
        self,
        symbol:             str,
        macro_tf:           str,
        micro_tf:           str,
        error_msg:          str,
        insufficient_pivots: bool = False,
    ) -> dict[str, Any]:
        log.error(f"[EWAOrchestrator] Error for {symbol}: {error_msg}")
        return {
            "symbol":             symbol,
            "macro_timeframe":    macro_tf,
            "micro_timeframe":    micro_tf,
            "analysis_ts":        int(time.time()),
            "error":              error_msg,
            "insufficient_pivots": insufficient_pivots,
            "current_price":      0.0,
            "pattern_type":       None,
            "pivots":             [],
            "scoring_matrix":     {"confidence_pct": 0},
            "targets":            {},
        }
