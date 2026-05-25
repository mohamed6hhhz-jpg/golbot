"""
ewa/target_engine.py

Phase 5/6: Target & Invalidation Price Engine
==============================================

OUTPUTS:
  - Strict Invalidation (Stop Loss): The price that, if closed beyond,
    mathematically disproves the current wave count. Derived from Elliott rules,
    not from arbitrary ATR multiples.

  - Primary Target (Projection): Fibonacci extension of the measured wave legs.

  - Extended Target: Secondary projection at a higher Fibonacci level.

MATHEMATICAL BASIS:
  IMPULSE targets:
    - Primary:  W4_end ± (W1_length × 1.000)   → W5 = W1 (equal move)
    - Extended: W4_end ± (W1_length × 1.618)   → W5 = 1.618 × W1
    - Invalidation: W0 price (origin of entire sequence — Rule 1 basis)

  CORRECTIVE ABC targets:
    - Primary:  B_end ± (A_length × 1.000)     → C = A (flat)
    - Extended: B_end ± (A_length × 1.618)     → C = 1.618 × A (zigzag)
    - Invalidation: B_end (Rule: B cannot exceed origin of correction)

  DIAGONAL targets:
    - Same as impulse but with W4/W1 overlap accepted
    - Apply 0.618 compression factor on W5 projection (diagonals truncate)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .pivot_engine import Pivot
from .elliott_guard import ElliottGuardResult, PatternType, Direction

log = logging.getLogger(__name__)


# ─── Types ────────────────────────────────────────────────────────────────────

@dataclass
class TargetResult:
    """
    Price level targets and invalidation for a validated wave count.
    All prices are raw floats — formatting happens in the JSON builder.
    """
    # Invalidation (Strict Stop Loss)
    invalidation_price:  float
    invalidation_label:  str    # Pre-formatted e.g. "$67,430.99"

    # Primary projection
    target_price:        float
    target_label:        str
    target_pct_move:     str    # e.g. "2.16%-" or "326.48%+"

    # Extended projection (secondary — higher Fibonacci level)
    extended_target:     Optional[float] = None
    extended_label:      Optional[str]   = None

    # Fibonacci level used for primary projection
    fib_level_primary:   float = 1.0
    fib_level_extended:  float = 1.618

    # Distance from current price to targets (for risk/reward display)
    risk_pct:            float = 0.0    # % distance to invalidation
    reward_pct:          float = 0.0    # % distance to primary target
    risk_reward_ratio:   float = 0.0   # reward / risk

    def to_dict(self) -> dict:
        d = {
            "invalidation_price":  round(self.invalidation_price, 8),
            "invalidation_label":  self.invalidation_label,
            "target_price":        round(self.target_price, 8),
            "target_label":        self.target_label,
            "target_pct_move":     self.target_pct_move,
            "fib_level_primary":   self.fib_level_primary,
            "fib_level_extended":  self.fib_level_extended,
            "risk_pct":            round(self.risk_pct, 4),
            "reward_pct":          round(self.reward_pct, 4),
            "risk_reward_ratio":   round(self.risk_reward_ratio, 2),
        }
        if self.extended_target is not None:
            d["extended_target"] = round(self.extended_target, 8)
            d["extended_label"]  = self.extended_label
        return d


# ─── Formatting Helpers ───────────────────────────────────────────────────────

def _fmt_price(price: float) -> str:
    """Format a price for display. High prices use commas; micro-caps use decimals."""
    if price >= 1_000:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:.4f}"
    elif price >= 0.01:
        return f"${price:.5f}"
    else:
        return f"${price:.8f}"


def _fmt_pct(pct: float, is_bearish: bool) -> str:
    """Format percentage move with directional suffix matching the UI images."""
    sign = "-" if is_bearish else "+"
    return f"{abs(pct):.2f}%{sign}"


def _compute_rr(
    current_price: float,
    target_price:  float,
    invalidation:  float,
    direction:     Direction,
) -> tuple[float, float, float]:
    """
    Compute risk %, reward %, and risk/reward ratio from current price.
    Returns (risk_pct, reward_pct, rr_ratio).
    """
    if current_price <= 0:
        return 0.0, 0.0, 0.0

    risk_pct   = abs(invalidation - current_price) / current_price * 100
    reward_pct = abs(target_price - current_price) / current_price * 100
    rr_ratio   = reward_pct / risk_pct if risk_pct > 0 else 0.0

    return round(risk_pct, 4), round(reward_pct, 4), round(rr_ratio, 2)


# ─── Target Engine ────────────────────────────────────────────────────────────

class TargetEngine:
    """
    Computes strict invalidation levels and Fibonacci-based price targets
    from a validated ElliottGuardResult.
    """

    def compute(
        self,
        guard_result:  ElliottGuardResult,
        current_price: float,
    ) -> TargetResult:
        """
        Dispatch to the appropriate computation method based on pattern type.

        Parameters
        ----------
        guard_result  : Validated wave count (must have valid=True)
        current_price : Latest closed bar close price (for R/R calculation)
        """
        if not guard_result.valid or not guard_result.pivots:
            return self._empty_result()

        ptype = guard_result.pattern_type
        direction = guard_result.direction

        if ptype in ("impulse",):
            return self._compute_impulse(guard_result.pivots, direction, current_price)

        elif ptype in ("diagonal_ending", "diagonal_leading"):
            return self._compute_diagonal(guard_result.pivots, direction, current_price)

        elif ptype in ("corrective_abc", "zigzag"):
            return self._compute_zigzag(guard_result.pivots, direction, current_price)

        elif ptype == "flat":
            return self._compute_flat(guard_result.pivots, direction, current_price)

        else:
            # Fallback: treat as impulse
            return self._compute_impulse(guard_result.pivots, direction, current_price)

    # ─── Impulse (5-wave) ──────────────────────────────────────────────────

    def _compute_impulse(
        self,
        pivots:        list[Pivot],
        direction:     Direction,
        current_price: float,
    ) -> TargetResult:
        """
        5-wave impulse targets.

        Invalidation: Wave 0 price (origin — Rule 1 basis).
        Primary target: Wave 4 end ± (W1_length × 1.000)
        Extended target: Wave 4 end ± (W1_length × 1.618)

        For a COMPLETE 5-wave (6 pivots including W0):
            We project from W4 where W5 should end.

        For an IN-PROGRESS count (fewer pivots):
            We project from the last known pivot using the last measured leg.
        """
        if len(pivots) < 4:
            return self._empty_result()

        is_bearish = direction == "bearish"
        w0 = pivots[0]

        # Invalidation = W0 price (mathematically proven by Rule 1)
        invalidation = w0.price

        if len(pivots) >= 6:
            # Complete 6-pivot count: project W5 from W4
            w1, w4 = pivots[1], pivots[4]
            w1_length = abs(w1.price - w0.price)

            if is_bearish:
                # W4 is a peak (relief rally) — W5 drops from W4
                primary_target  = w4.price - (w1_length * 1.000)
                extended_target = w4.price - (w1_length * 1.618)
            else:
                # W4 is a valley — W5 pushes up from W4
                primary_target  = w4.price + (w1_length * 1.000)
                extended_target = w4.price + (w1_length * 1.618)

        elif len(pivots) >= 4:
            # Partial count: project from last complete leg
            last_leg_start = pivots[-2]
            last_leg_end   = pivots[-1]
            leg_length     = abs(last_leg_end.price - last_leg_start.price)

            if is_bearish:
                primary_target  = last_leg_end.price - (leg_length * 0.618)
                extended_target = last_leg_end.price - (leg_length * 1.000)
            else:
                primary_target  = last_leg_end.price + (leg_length * 0.618)
                extended_target = last_leg_end.price + (leg_length * 1.000)
        else:
            return self._empty_result()

        # Compute % move from current price
        pct_move = (primary_target - current_price) / current_price * 100 \
                   if current_price > 0 else 0.0

        risk_pct, reward_pct, rr_ratio = _compute_rr(
            current_price, primary_target, invalidation, direction
        )

        log.debug(
            f"[TargetEngine] Impulse {direction}: "
            f"INV={invalidation:.4f} TGT={primary_target:.4f} "
            f"EXT={extended_target:.4f} R/R={rr_ratio:.2f}"
        )

        return TargetResult(
            invalidation_price=round(invalidation, 8),
            invalidation_label=_fmt_price(invalidation),
            target_price=round(primary_target, 8),
            target_label=_fmt_price(primary_target),
            target_pct_move=_fmt_pct(pct_move, is_bearish),
            extended_target=round(extended_target, 8),
            extended_label=_fmt_price(extended_target),
            fib_level_primary=1.000,
            fib_level_extended=1.618,
            risk_pct=risk_pct,
            reward_pct=reward_pct,
            risk_reward_ratio=rr_ratio,
        )

    # ─── Diagonal (5-wave with W4/W1 overlap) ──────────────────────────────

    def _compute_diagonal(
        self,
        pivots:        list[Pivot],
        direction:     Direction,
        current_price: float,
    ) -> TargetResult:
        """
        Diagonal triangle targets. Same structure as impulse but:
        - W5 often TRUNCATES (doesn't reach W5 = W1 projection)
        - Use 0.618× W1 as the conservative primary target
        - Invalidation = W0 origin (same as impulse Rule 1)
        """
        if len(pivots) < 4:
            return self._empty_result()

        is_bearish = direction == "bearish"
        w0 = pivots[0]
        invalidation = w0.price

        w1_length = abs(pivots[1].price - pivots[0].price)
        w4_end    = pivots[4].price if len(pivots) >= 5 else pivots[-1].price

        if is_bearish:
            primary_target  = w4_end - (w1_length * 0.618)  # Conservative for diagonal
            extended_target = w4_end - (w1_length * 1.000)
        else:
            primary_target  = w4_end + (w1_length * 0.618)
            extended_target = w4_end + (w1_length * 1.000)

        pct_move = (primary_target - current_price) / current_price * 100 \
                   if current_price > 0 else 0.0
        risk_pct, reward_pct, rr_ratio = _compute_rr(
            current_price, primary_target, invalidation, direction
        )

        return TargetResult(
            invalidation_price=round(invalidation, 8),
            invalidation_label=_fmt_price(invalidation),
            target_price=round(primary_target, 8),
            target_label=_fmt_price(primary_target),
            target_pct_move=_fmt_pct(pct_move, is_bearish),
            extended_target=round(extended_target, 8),
            extended_label=_fmt_price(extended_target),
            fib_level_primary=0.618,
            fib_level_extended=1.000,
            risk_pct=risk_pct,
            reward_pct=reward_pct,
            risk_reward_ratio=rr_ratio,
        )

    # ─── Zigzag A-B-C ──────────────────────────────────────────────────────

    def _compute_zigzag(
        self,
        pivots:        list[Pivot],
        direction:     Direction,
        current_price: float,
    ) -> TargetResult:
        """
        Zigzag A-B-C targets (C > A, impulsive C wave).

        Invalidation: B_end price (B cannot exceed correction origin — ABC-R1 basis).
        Primary:  B_end ± (A_length × 1.000)   → C = A in length
        Extended: B_end ± (A_length × 1.618)   → C = 1.618 × A
        """
        if len(pivots) < 3:
            return self._empty_result()

        is_bearish = direction == "bearish"
        origin = pivots[0]
        a_end  = pivots[1]
        b_end  = pivots[2]

        a_length = abs(a_end.price - origin.price)

        # Invalidation = B_end (ABC-R1: B cannot exceed correction origin)
        invalidation = b_end.price

        if is_bearish:
            primary_target  = b_end.price - (a_length * 1.000)
            extended_target = b_end.price - (a_length * 1.618)
        else:
            primary_target  = b_end.price + (a_length * 1.000)
            extended_target = b_end.price + (a_length * 1.618)

        pct_move = (primary_target - current_price) / current_price * 100 \
                   if current_price > 0 else 0.0
        risk_pct, reward_pct, rr_ratio = _compute_rr(
            current_price, primary_target, invalidation, direction
        )

        return TargetResult(
            invalidation_price=round(invalidation, 8),
            invalidation_label=_fmt_price(invalidation),
            target_price=round(primary_target, 8),
            target_label=_fmt_price(primary_target),
            target_pct_move=_fmt_pct(pct_move, is_bearish),
            extended_target=round(extended_target, 8),
            extended_label=_fmt_price(extended_target),
            fib_level_primary=1.000,
            fib_level_extended=1.618,
            risk_pct=risk_pct,
            reward_pct=reward_pct,
            risk_reward_ratio=rr_ratio,
        )

    # ─── Flat A-B-C ────────────────────────────────────────────────────────

    def _compute_flat(
        self,
        pivots:        list[Pivot],
        direction:     Direction,
        current_price: float,
    ) -> TargetResult:
        """
        Flat correction targets (C ≈ A, B retraces near 100% of A).
        Primary:  B_end ± (A_length × 1.000)   → C ≈ A (standard flat)
        Extended: B_end ± (A_length × 1.272)   → expanded flat
        """
        if len(pivots) < 3:
            return self._empty_result()

        is_bearish = direction == "bearish"
        origin = pivots[0]
        a_end  = pivots[1]
        b_end  = pivots[2]

        a_length = abs(a_end.price - origin.price)
        invalidation = b_end.price

        if is_bearish:
            primary_target  = b_end.price - (a_length * 1.000)
            extended_target = b_end.price - (a_length * 1.272)
        else:
            primary_target  = b_end.price + (a_length * 1.000)
            extended_target = b_end.price + (a_length * 1.272)

        pct_move = (primary_target - current_price) / current_price * 100 \
                   if current_price > 0 else 0.0
        risk_pct, reward_pct, rr_ratio = _compute_rr(
            current_price, primary_target, invalidation, direction
        )

        return TargetResult(
            invalidation_price=round(invalidation, 8),
            invalidation_label=_fmt_price(invalidation),
            target_price=round(primary_target, 8),
            target_label=_fmt_price(primary_target),
            target_pct_move=_fmt_pct(pct_move, is_bearish),
            extended_target=round(extended_target, 8),
            extended_label=_fmt_price(extended_target),
            fib_level_primary=1.000,
            fib_level_extended=1.272,
            risk_pct=risk_pct,
            reward_pct=reward_pct,
            risk_reward_ratio=rr_ratio,
        )

    # ─── Empty / Error ──────────────────────────────────────────────────────

    def _empty_result(self) -> TargetResult:
        """Return a zero-value TargetResult when computation is not possible."""
        return TargetResult(
            invalidation_price=0.0,
            invalidation_label="N/A",
            target_price=0.0,
            target_label="N/A",
            target_pct_move="0.00%",
        )
