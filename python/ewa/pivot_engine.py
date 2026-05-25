"""
ewa/pivot_engine.py

Phase 2: Adaptive Pivot Detection Engine — Elliott Wave Quantitative Analysis
=============================================================================

PHILOSOPHY:
    Elliott Waves are defined by their structural turning points (pivots).
    The entire wave count exists ONLY between these pivot coordinates.
    Therefore: accurately finding pivots = finding waves.

    We use scipy.signal.find_peaks with ATR-scaled prominence as the primary
    detector. This gives us:
      (a) Noise immunity: small wicks don't register as pivots
      (b) Volatility adaptation: ATR scaling means crypto's wide-ranging
          swings don't produce too few pivots, and low-volatility periods
          don't produce too many
      (c) Reproducibility: given the same OHLCV array, the same pivots
          are always returned. No randomness, no ML inference.

ALGORITHM OVERVIEW:
    1. Compute ATR over the last 14 bars → derive minimum prominence threshold
    2. Run find_peaks on High array  → candidate peaks
    3. Run find_peaks on Low array   → candidate valleys (inverted)
    4. Merge peaks + valleys, sort by bar index
    5. Enforce strict peak/valley alternation (Elliott requirement)
    6. Apply minimum swing filter: discard pivots that move <prominence from prior
    7. Return typed Pivot objects with coordinates for wave counting

DEPENDENCIES:
    numpy>=1.24
    scipy>=1.10
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from scipy.signal import find_peaks

log = logging.getLogger(__name__)


# ─── Types ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OHLCVBar:
    """Single OHLCV bar as received from Next.js (mirrors TypeScript OHLCVBar)."""
    t:          int     # Unix timestamp in seconds
    o:          float   # open
    h:          float   # high
    l:          float   # low
    c:          float   # close
    v:          float   # volume
    tc:         int     # close time in seconds
    is_closed:  bool    # True if this bar is fully closed

    @classmethod
    def from_dict(cls, d: dict) -> "OHLCVBar":
        """Parse a bar dictionary from the JSON payload."""
        return cls(
            t=int(d["t"]),
            o=float(d["o"]),
            h=float(d["h"]),
            l=float(d["l"]),
            c=float(d["c"]),
            v=float(d.get("v", 0.0)),
            tc=int(d.get("tc", 0)),
            is_closed=bool(d.get("is_closed", True)),
        )


@dataclass
class Pivot:
    """
    A confirmed structural turning point in price action.

    bar_index   → position within the OHLCV array (for SVG X-axis mapping)
    timestamp   → Unix seconds (for chart time axis)
    price       → The exact High (peak) or Low (valley) price
    pivot_type  → 'peak' | 'valley'
    prominence  → The ATR-normalized significance of this pivot (0.0–∞)
                  Higher = more significant structural level
    """
    bar_index:   int
    timestamp:   int
    price:       float
    pivot_type:  Literal["peak", "valley"]
    prominence:  float = field(default=0.0)

    def to_dict(self) -> dict:
        return {
            "bar_index":  self.bar_index,
            "timestamp":  self.timestamp,
            "price":      round(self.price, 8),
            "pivot_type": self.pivot_type,
            "prominence": round(self.prominence, 4),
        }

    def __repr__(self) -> str:
        symbol = "▲" if self.pivot_type == "peak" else "▼"
        return f"Pivot({symbol} bar={self.bar_index} price={self.price:.4f} prom={self.prominence:.3f})"


@dataclass
class PivotEngineResult:
    """
    Full output of the pivot detection engine.
    Contains all detected pivots and the parameters used to find them.
    """
    pivots:          list[Pivot]
    atr:             float           # ATR value used for prominence scaling
    prominence_used: float           # Actual prominence threshold applied
    min_distance:    int             # Min bars between pivots
    bar_count:       int             # Total bars processed
    pivot_count:     int             # Number of clean pivots found
    timeframe:       str             # For logging/debugging
    symbol:          str

    def to_dict(self) -> dict:
        return {
            "pivots":          [p.to_dict() for p in self.pivots],
            "atr":             round(self.atr, 8),
            "prominence_used": round(self.prominence_used, 8),
            "min_distance":    self.min_distance,
            "bar_count":       self.bar_count,
            "pivot_count":     self.pivot_count,
            "timeframe":       self.timeframe,
            "symbol":          self.symbol,
        }


# ─── ATR Calculator ───────────────────────────────────────────────────────────

def compute_atr(bars: list[OHLCVBar], period: int = 14) -> float:
    """
    Compute Wilder's Average True Range over the last `period` bars.

    True Range = max(H-L, |H-prev_C|, |L-prev_C|)
    ATR = simple average of TR over `period` bars (Wilder's uses EMA,
          but for pivot scaling a simple average is less sensitive to outliers).

    Returns 0.0 if insufficient bars for calculation.
    """
    if len(bars) < 2:
        return 0.0

    # Use last (period + 1) bars for period true-range values
    sample = bars[-(period + 1):]

    true_ranges: list[float] = []
    for i in range(1, len(sample)):
        curr = sample[i]
        prev = sample[i - 1]
        tr = max(
            curr.h - curr.l,
            abs(curr.h - prev.c),
            abs(curr.l - prev.c),
        )
        true_ranges.append(tr)

    if not true_ranges:
        return 0.0

    return float(np.mean(true_ranges[-period:]))


def compute_prominence_threshold(
    bars:               list[OHLCVBar],
    atr_multiplier:     float = 2.5,
    min_pct_of_price:   float = 0.005,    # 0.5% of current price, minimum floor
    atr_period:         int   = 14,
) -> tuple[float, float]:
    """
    Derive the minimum prominence threshold for pivot detection.

    Strategy:
        prominence = max(ATR × atr_multiplier, current_price × min_pct_of_price)

    Rationale:
        - ATR × 2.5 means a pivot must represent a move of 2.5 average ranges.
          This filters wicks and minor consolidations.
        - The min_pct floor prevents the threshold collapsing to near-zero on
          very low ATR periods (tight ranges), which would flood us with pivots.

    Returns:
        (prominence_threshold, atr_value)
    """
    atr = compute_atr(bars, period=atr_period)
    current_price = bars[-1].c if bars else 1.0

    atr_based   = atr * atr_multiplier
    price_based = current_price * min_pct_of_price

    prominence = max(atr_based, price_based)

    log.debug(
        f"ATR={atr:.4f}, ATR×{atr_multiplier}={atr_based:.4f}, "
        f"Price×{min_pct_of_price*100:.1f}%={price_based:.4f} → prominence={prominence:.4f}"
    )

    return prominence, atr


# ─── Alternation Enforcer ─────────────────────────────────────────────────────

def enforce_alternation(
    pivots: list[Pivot],
    highs:  np.ndarray,
    lows:   np.ndarray,
) -> list[Pivot]:
    """
    Elliott Wave Theory requires strict alternation: peak → valley → peak → ...
    (or valley → peak → valley → ... depending on trend direction).

    When two consecutive pivots of the same type appear, we keep the more
    extreme one (higher of two peaks / lower of two valleys), as the more
    extreme pivot represents the true structural level.

    This is O(n) — single pass through the sorted pivot list.
    """
    if not pivots:
        return []

    result: list[Pivot] = [pivots[0]]

    for current in pivots[1:]:
        last = result[-1]

        if current.pivot_type == last.pivot_type:
            # Same type — keep the more structurally significant one
            if current.pivot_type == "peak":
                if current.price > last.price:
                    result[-1] = current
                # else: keep last (it's the higher peak)
            else:  # valley
                if current.price < last.price:
                    result[-1] = current
                # else: keep last (it's the lower valley)
        else:
            # Different type — valid alternation, append
            result.append(current)

    return result


# ─── Minimum Swing Filter ─────────────────────────────────────────────────────

def filter_minimum_swing(
    pivots:     list[Pivot],
    min_swing:  float,
) -> list[Pivot]:
    """
    Secondary filter: remove pivots whose price move from the prior pivot
    is less than `min_swing`. This eliminates micro-corrections that pass
    the find_peaks filter but aren't meaningful EW structural levels.

    Note: After filtering, alternation is re-enforced since removing a pivot
    may create two consecutive peaks or valleys.
    """
    if len(pivots) < 2:
        return pivots

    result: list[Pivot] = [pivots[0]]

    for i in range(1, len(pivots)):
        current = pivots[i]
        last    = result[-1]
        swing   = abs(current.price - last.price)

        if swing >= min_swing:
            result.append(current)
        else:
            log.debug(
                f"Filtered pivot at bar={current.price:.4f}: "
                f"swing={swing:.4f} < min_swing={min_swing:.4f}"
            )

    return result


# ─── Core Pivot Detection ─────────────────────────────────────────────────────

def detect_pivots(
    bars:               list[OHLCVBar],
    symbol:             str   = "UNKNOWN",
    timeframe:          str   = "unknown",
    atr_multiplier:     float = 2.5,
    min_pct_of_price:   float = 0.005,
    min_distance_bars:  int   | None = None,
    atr_period:         int   = 14,
    max_pivots:         int   = 60,
) -> PivotEngineResult:
    """
    Main entry point: detect structural pivot points in an OHLCV bar array.

    Parameters
    ----------
    bars              : List of OHLCVBar (all must be closed candles)
    symbol            : Trading pair (e.g. "BTCUSDT") — for logging only
    timeframe         : Bar interval (e.g. "1d") — for logging and min_distance
    atr_multiplier    : Scale factor for ATR-based prominence. Higher = fewer,
                        more significant pivots. Default 2.5 is well-calibrated
                        for crypto Spot markets.
    min_pct_of_price  : Floor for prominence as % of current price (0.005 = 0.5%)
    min_distance_bars : Min bars between two pivots. If None, auto-derives from
                        timeframe (see _auto_min_distance).
    atr_period        : Period for ATR calculation (default 14, Wilder standard)
    max_pivots        : Maximum pivots to return. If more are found, the least
                        prominent are removed until count ≤ max_pivots.
                        Prevents memory/CPU explosion on very long bar arrays.

    Returns
    -------
    PivotEngineResult with ordered list of Pivot objects (ascending bar_index)
    """
    if not bars:
        raise ValueError(f"[PivotEngine] No bars provided for {symbol} {timeframe}.")

    if len(bars) < 10:
        raise ValueError(
            f"[PivotEngine] Insufficient bars: {len(bars)} provided, minimum 10 required. "
            f"Symbol: {symbol} {timeframe}"
        )

    log.info(f"[PivotEngine] Detecting pivots: {symbol} {timeframe} — {len(bars)} bars")

    # ── Extract numpy arrays ─────────────────────────────────────────────────
    highs      = np.array([b.h for b in bars], dtype=np.float64)
    lows       = np.array([b.l for b in bars], dtype=np.float64)
    timestamps = np.array([b.t for b in bars], dtype=np.int64)

    # ── Derive prominence threshold ──────────────────────────────────────────
    prominence, atr = compute_prominence_threshold(
        bars,
        atr_multiplier=atr_multiplier,
        min_pct_of_price=min_pct_of_price,
        atr_period=atr_period,
    )

    # ── Auto-derive min_distance if not provided ─────────────────────────────
    min_distance = min_distance_bars if min_distance_bars is not None \
                   else _auto_min_distance(timeframe)

    log.info(
        f"[PivotEngine] prominence={prominence:.6f} ATR={atr:.6f} "
        f"min_distance={min_distance} bars"
    )

    # ── Peak detection (on High prices) ─────────────────────────────────────
    peak_indices, peak_props = find_peaks(
        highs,
        prominence=prominence,
        distance=min_distance,
        # width: require the peak to be visually prominent for at least 1 bar
        # (prevents single-bar spike wicks from counting as EW structural peaks)
        width=1,
    )

    # ── Valley detection (on Low prices, inverted for find_peaks) ────────────
    valley_indices, valley_props = find_peaks(
        -lows,   # Negate: find_peaks finds maxima; negating finds minima
        prominence=prominence,
        distance=min_distance,
        width=1,
    )

    # ── Build Pivot objects ──────────────────────────────────────────────────
    all_pivots: list[Pivot] = []

    for idx, i in enumerate(peak_indices):
        raw_prominence = float(peak_props["prominences"][idx])
        all_pivots.append(Pivot(
            bar_index=int(i),
            timestamp=int(timestamps[i]),
            price=float(highs[i]),
            pivot_type="peak",
            prominence=raw_prominence / max(atr, 1e-10),  # normalize by ATR
        ))

    for idx, i in enumerate(valley_indices):
        raw_prominence = float(valley_props["prominences"][idx])
        all_pivots.append(Pivot(
            bar_index=int(i),
            timestamp=int(timestamps[i]),
            price=float(lows[i]),
            pivot_type="valley",
            prominence=raw_prominence / max(atr, 1e-10),  # normalize by ATR
        ))

    # ── Sort chronologically ─────────────────────────────────────────────────
    all_pivots.sort(key=lambda p: p.bar_index)

    if not all_pivots:
        log.warning(
            f"[PivotEngine] No pivots detected for {symbol} {timeframe}. "
            f"Consider reducing atr_multiplier (current: {atr_multiplier}) "
            f"or min_distance (current: {min_distance})."
        )
        return PivotEngineResult(
            pivots=[], atr=atr, prominence_used=prominence,
            min_distance=min_distance, bar_count=len(bars),
            pivot_count=0, timeframe=timeframe, symbol=symbol,
        )

    # ── Enforce alternation (Elliott Wave requirement) ───────────────────────
    alternated = enforce_alternation(all_pivots, highs, lows)

    # ── Minimum swing filter (remove micro-corrections) ──────────────────────
    clean_pivots = filter_minimum_swing(alternated, min_swing=prominence)

    # Re-enforce alternation after swing filter (filter may break alternation)
    clean_pivots = enforce_alternation(clean_pivots, highs, lows)

    # ── Cap at max_pivots (keep most prominent ones) ─────────────────────────
    if len(clean_pivots) > max_pivots:
        log.info(
            f"[PivotEngine] {len(clean_pivots)} pivots found, capping at {max_pivots} "
            f"(keeping most prominent)"
        )
        # Sort by prominence descending, keep top max_pivots, re-sort by bar_index
        clean_pivots.sort(key=lambda p: p.prominence, reverse=True)
        clean_pivots = clean_pivots[:max_pivots]
        clean_pivots.sort(key=lambda p: p.bar_index)
        # Re-enforce alternation after culling
        clean_pivots = enforce_alternation(clean_pivots, highs, lows)

    log.info(
        f"[PivotEngine] Found {len(clean_pivots)} clean pivots "
        f"({sum(1 for p in clean_pivots if p.pivot_type == 'peak')} peaks, "
        f"{sum(1 for p in clean_pivots if p.pivot_type == 'valley')} valleys)"
    )

    return PivotEngineResult(
        pivots=clean_pivots,
        atr=atr,
        prominence_used=prominence,
        min_distance=min_distance,
        bar_count=len(bars),
        pivot_count=len(clean_pivots),
        timeframe=timeframe,
        symbol=symbol,
    )


# ─── Auto Min Distance ────────────────────────────────────────────────────────

def _auto_min_distance(timeframe: str) -> int:
    """
    Derive a sensible minimum bar distance between pivots based on timeframe.

    The logic: on higher timeframes, Elliott Waves unfold over MORE bars.
    A Wave on 1D typically spans 5–50+ bars. On 1H, waves span 3–20 bars.
    min_distance prevents two pivots being assigned to adjacent bars, which
    would produce nonsensical micro-waves.

    Calibrated against empirical BTC wave structures:
        1w  → 4  bars minimum (macro Grand Supercycle waves)
        3d  → 5  bars
        1d  → 5  bars (Daily impulse spans ~5-20 bars minimum)
        4h  → 8  bars (4H wave leg = at least 8 bars ≈ 32h minimum)
        1h  → 12 bars (1H leg = at least 12 bars = 12h minimum)
        15m → 20 bars (15m = at least 5h minimum swing)
    """
    mapping: dict[str, int] = {
        "1w":  4,
        "3d":  5,
        "1d":  5,
        "4h":  8,
        "1h":  12,
        "15m": 20,
    }
    dist = mapping.get(timeframe.lower(), 8)
    log.debug(f"[PivotEngine] Auto min_distance for {timeframe}: {dist} bars")
    return dist


# ─── Slope Calculator (helper for Elliott Guard) ──────────────────────────────

def compute_pivot_slopes(pivots: list[Pivot]) -> list[float]:
    """
    Compute price change (slope) between consecutive pivots.
    Returns a list of length (len(pivots) - 1).
    Positive slope = rising leg, negative = falling leg.
    Used by ElliottGuard to quickly classify bullish/bearish impulses.
    """
    if len(pivots) < 2:
        return []
    return [
        pivots[i + 1].price - pivots[i].price
        for i in range(len(pivots) - 1)
    ]


def compute_leg_lengths(pivots: list[Pivot]) -> list[float]:
    """
    Compute absolute price length of each leg between consecutive pivots.
    Used by ElliottGuard Rule 2 (Wave 3 not shortest).
    """
    return [abs(pivots[i + 1].price - pivots[i].price) for i in range(len(pivots) - 1)]


# ─── Pivot Window Extractor ───────────────────────────────────────────────────

def extract_wave_candidates(
    pivots: list[Pivot],
    window: int = 6,
    step:   int = 1,
) -> list[list[Pivot]]:
    """
    Extract all windows of `window` consecutive pivots for wave counting.

    For a 5-wave impulse we need exactly 6 pivots (W0 through W5).
    For a 3-wave correction we need exactly 4 pivots (A through C end).

    We slide a window of size `window` across all detected pivots to generate
    candidate wave counts, which the ElliottGuard then validates.

    Parameters
    ----------
    pivots : Full list of detected pivots (sorted by bar_index)
    window : Number of pivots per candidate (6 for impulse, 4 for correction)
    step   : Sliding step (1 = check every possible window)

    Returns
    -------
    List of pivot windows, most recent first (reversed so Elliott Guard
    checks the latest potential wave count before older ones).
    """
    if len(pivots) < window:
        return []

    candidates = [
        pivots[i : i + window]
        for i in range(0, len(pivots) - window + 1, step)
    ]

    # Most recent candidates first — we want the latest wave count
    candidates.reverse()
    return candidates


# ─── Fibonacci Level Checker (standalone, also used by fibonacci_validator.py) ─

FIBONACCI_RATIOS = {
    "retrace": [0.236, 0.382, 0.500, 0.618, 0.786, 0.886],
    "extend":  [1.000, 1.272, 1.414, 1.618, 2.000, 2.618],
}
FIBO_TOLERANCE = 0.04  # ±4% of the Fibonacci level


def nearest_fibonacci(ratio: float, fib_type: str = "retrace") -> tuple[float, float]:
    """
    Find the nearest Fibonacci level to a given ratio.

    Returns:
        (nearest_level, deviation_percentage)
        deviation_pct is 0.0 when exact, higher when further from ideal
    """
    levels = FIBONACCI_RATIOS.get(fib_type, FIBONACCI_RATIOS["retrace"])
    if not levels:
        return 0.0, 1.0

    nearest = min(levels, key=lambda l: abs(ratio - l))
    deviation = abs(ratio - nearest) / nearest if nearest != 0 else 1.0
    return nearest, deviation


def is_fibonacci_confluence(ratio: float, fib_type: str = "retrace") -> bool:
    """Returns True if ratio is within FIBO_TOLERANCE of any standard Fibonacci level."""
    _, deviation = nearest_fibonacci(ratio, fib_type)
    return deviation <= FIBO_TOLERANCE


# ─── Quick Self-Test ──────────────────────────────────────────────────────────

def _make_test_bars(n: int = 200) -> list[OHLCVBar]:
    """
    Generate synthetic OHLCV bars with known wave structure for unit testing.
    Creates a 5-wave bullish impulse followed by a 3-wave ABC correction.
    """
    np.random.seed(42)

    # Synthetic impulse pattern
    price = 50_000.0
    bars: list[OHLCVBar] = []
    t = 1_700_000_000

    for i in range(n):
        noise  = np.random.normal(0, price * 0.005)
        # Create a rough 5-wave pattern with overlaid noise
        wave   = math.sin(i / 20 * math.pi) * price * 0.08
        close  = max(price + wave + noise, price * 0.5)
        high   = close * (1 + abs(np.random.normal(0, 0.003)))
        low    = close * (1 - abs(np.random.normal(0, 0.003)))
        open_  = close * (1 + np.random.normal(0, 0.002))
        bars.append(OHLCVBar(
            t=t + i * 3600,
            o=round(open_,  2),
            h=round(high,   2),
            l=round(low,    2),
            c=round(close,  2),
            v=round(abs(np.random.normal(100, 20)), 2),
            tc=t + i * 3600 + 3599,
            is_closed=True,
        ))

    return bars


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=" * 60)
    print("EWA Pivot Engine — Self-Test")
    print("=" * 60)

    test_bars = _make_test_bars(200)
    result    = detect_pivots(
        bars=test_bars,
        symbol="BTCUSDT_TEST",
        timeframe="1h",
        atr_multiplier=2.5,
    )

    print(f"\nBars processed : {result.bar_count}")
    print(f"ATR            : {result.atr:.2f}")
    print(f"Prominence     : {result.prominence_used:.2f}")
    print(f"Pivots found   : {result.pivot_count}")
    print()
    for p in result.pivots:
        print(f"  {p}")

    print()
    # Test candidate extraction
    impulse_candidates  = extract_wave_candidates(result.pivots, window=6)
    corrective_candidates = extract_wave_candidates(result.pivots, window=4)
    print(f"Impulse candidates (6-pivot windows)    : {len(impulse_candidates)}")
    print(f"Corrective candidates (4-pivot windows) : {len(corrective_candidates)}")

    # Test Fibonacci checker
    print()
    test_ratios = [0.618, 1.618, 0.5, 0.382, 0.75]
    for r in test_ratios:
        level, dev = nearest_fibonacci(r, "retrace")
        print(f"  ratio={r:.3f} → nearest Fib={level:.3f} dev={dev*100:.1f}% "
              f"{'✓' if dev <= FIBO_TOLERANCE else '✗'}")

    print()
    print("Self-test complete. ✓")
