"""
ewa/elliott_guard.py

Phase 3: The Elliott Guard — Strict Rules Engine
=================================================

PHILOSOPHY:
    Elliott Wave Theory has exactly 3 inviolable rules. These are not
    guidelines — they are mathematical invariants. If ANY rule is violated,
    the wave count scenario is IMMEDIATELY discarded (fail-fast).

    Beyond the 3 rules, there are well-established guidelines that increase
    or decrease confidence in a wave count. We model these as a scoring
    system: violations don't discard the count, but reduce its score.

THE 3 INVIOLABLE RULES (Robert Prechter, "Elliott Wave Principle"):
    Rule 1: Wave 2 can NEVER retrace beyond the origin of Wave 1.
            (For bullish: W2 end > W0 start. For bearish: W2 end < W0 start)
    Rule 2: Wave 3 is NEVER the shortest of Waves 1, 3, and 5.
            (len(W3) >= min(len(W1), len(W5)) — at least one must be shorter)
    Rule 3: Wave 4 can NEVER enter the price territory of Wave 1.
            (For bullish: W4 end > W1 end. For bearish: W4 end < W1 end)
            Exception: diagonal triangles (handled separately with reduced score)

SUPPORTED PATTERNS:
    IMPULSE (5-wave):   W0 → W1 → W2 → W3 → W4 → W5   (6 pivots)
    CORRECTIVE ABC:     W0 → A  → B  → C  → End        (4 pivots)
    DIAGONAL:           5-wave but with W4/W1 overlap   (score penalty, not discard)

SCORING COMPONENTS (from Phase 5 JSON schema, 40-point rules block):
    Rule 1 pass    : mandatory (discard if fail)
    Rule 2 pass    : mandatory (discard if fail)
    Rule 3 pass    : mandatory (discard if fail, unless diagonal)
    All rules pass : 40 / 40 points
    Guidelines     : contribute to fibonacci/structure blocks (separate)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from .pivot_engine import (
    Pivot,
    compute_leg_lengths,
    compute_pivot_slopes,
    nearest_fibonacci,
    is_fibonacci_confluence,
    FIBO_TOLERANCE,
)

log = logging.getLogger(__name__)


# ─── Types ────────────────────────────────────────────────────────────────────

PatternType = Literal["impulse", "corrective_abc", "diagonal_ending",
                      "diagonal_leading", "zigzag", "flat", "triangle"]

Direction   = Literal["bullish", "bearish"]


@dataclass
class RuleResult:
    """Result of a single Elliott Wave rule check."""
    rule_id:     str
    rule_name:   str
    passed:      bool
    detail:      str        # Human-readable explanation for debugging
    is_critical: bool       # If True, failure = immediate discard


@dataclass
class GuidelineResult:
    """Result of a single Elliott Wave guideline check."""
    guideline_id:  str
    guideline_name: str
    passed:        bool
    ratio:         float       # Actual measured ratio
    ideal_ratio:   float       # Nearest Fibonacci level
    deviation_pct: float       # % deviation from ideal
    score:         float       # 0.0 – 1.0 contribution to structure score


@dataclass
class ElliottGuardResult:
    """
    Full validation result for a candidate wave count (one set of pivots).

    valid          : True if all 3 inviolable rules pass
    pattern_type   : Classified pattern type
    direction      : bullish / bearish
    rules          : List of RuleResult (3 critical + optional diagonal check)
    guidelines     : List of GuidelineResult (Fibonacci relations)
    rules_score    : 0 or 40 (binary — all rules pass or all fail)
    structure_score: 0–20 (based on wave structure quality)
    fib_score      : 0–25 (based on Fibonacci relation quality)
    is_diagonal    : True if Wave 4 overlaps Wave 1 (diagonal pattern)
    current_wave   : The wave label currently in progress (for MTF context)
    invalidation   : The price level that mathematically invalidates this count
    """
    valid:            bool
    pattern_type:     PatternType
    direction:        Direction
    rules:            list[RuleResult]    = field(default_factory=list)
    guidelines:       list[GuidelineResult] = field(default_factory=list)
    rules_score:      int   = 0           # 0 or 40
    structure_score:  int   = 0           # 0–20
    fib_score:        int   = 0           # 0–25
    is_diagonal:      bool  = False
    current_wave:     str   = ""          # "3", "4", "C", etc.
    invalidation:     float = 0.0
    base_score:       int   = 0           # rules + structure (before MTF/momentum)
    reject_reason:    str   = ""          # Why it was discarded (if not valid)
    pivots:           list[Pivot] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid":           self.valid,
            "pattern_type":    self.pattern_type,
            "direction":       self.direction,
            "rules_score":     self.rules_score,
            "structure_score": self.structure_score,
            "fib_score":       self.fib_score,
            "is_diagonal":     self.is_diagonal,
            "current_wave":    self.current_wave,
            "invalidation":    round(self.invalidation, 8),
            "base_score":      self.base_score,
            "reject_reason":   self.reject_reason,
            "rules": [
                {
                    "id":          r.rule_id,
                    "name":        r.rule_name,
                    "passed":      r.passed,
                    "detail":      r.detail,
                    "is_critical": r.is_critical,
                }
                for r in self.rules
            ],
            "guidelines": [
                {
                    "id":           g.guideline_id,
                    "name":         g.guideline_name,
                    "passed":       g.passed,
                    "ratio":        round(g.ratio, 4),
                    "ideal_ratio":  round(g.ideal_ratio, 4),
                    "deviation_pct":round(g.deviation_pct, 2),
                    "score":        round(g.score, 3),
                }
                for g in self.guidelines
            ],
        }


# ─── Direction Classifier ─────────────────────────────────────────────────────

def _classify_direction(pivots: list[Pivot]) -> Direction:
    """
    Determine whether a sequence of pivots is bullish or bearish.
    Uses the net price move from first to last pivot.
    A bullish impulse starts at a valley and ends at a peak.
    A bearish impulse starts at a peak and ends at a valley.
    """
    if not pivots:
        raise ValueError("Cannot classify direction of empty pivot list.")
    net = pivots[-1].price - pivots[0].price
    return "bullish" if net > 0 else "bearish"


# ─── Elliott Guard ────────────────────────────────────────────────────────────

class ElliottGuard:
    """
    Validates a candidate set of pivots against Elliott Wave Theory rules.

    Usage:
        guard = ElliottGuard()
        result = guard.validate_impulse(pivots_6)    # 5-wave impulse
        result = guard.validate_corrective(pivots_4) # A-B-C correction
    """

    # ═══════════════════════════════════════════════════════════════════════
    #  INVIOLABLE RULES — failure = immediate discard
    # ═══════════════════════════════════════════════════════════════════════

    def _rule_1_wave2_no_full_retrace(
        self,
        w0: Pivot,
        w1: Pivot,
        w2: Pivot,
        direction: Direction,
    ) -> RuleResult:
        """
        Rule 1: Wave 2 cannot retrace 100% of Wave 1.
        The origin of Wave 1 (W0) is the absolute invalidation level.
        For bullish: W2 must stay ABOVE W0 price.
        For bearish: W2 must stay BELOW W0 price.
        """
        if direction == "bullish":
            passes = w2.price > w0.price
            detail = (
                f"W2={w2.price:.4f} {'>' if passes else '<='} W0={w0.price:.4f} "
                f"({'PASS' if passes else 'FAIL — W2 crossed below W0 origin'})"
            )
        else:
            passes = w2.price < w0.price
            detail = (
                f"W2={w2.price:.4f} {'<' if passes else '>='} W0={w0.price:.4f} "
                f"({'PASS' if passes else 'FAIL — W2 crossed above W0 origin'})"
            )

        return RuleResult(
            rule_id="R1",
            rule_name="Wave 2 cannot retrace past Wave 1 origin",
            passed=passes,
            detail=detail,
            is_critical=True,
        )

    def _rule_2_wave3_not_shortest(
        self,
        w0: Pivot,
        w1: Pivot,
        w2: Pivot,
        w3: Pivot,
        w4: Pivot,
        w5: Pivot,
    ) -> RuleResult:
        """
        Rule 2: Wave 3 is NEVER the shortest of Waves 1, 3, and 5.
        We compute absolute price length of each impulse leg.
        Wave 3 passes if it is NOT simultaneously shorter than both W1 and W5.
        """
        len_w1 = abs(w1.price - w0.price)
        len_w3 = abs(w3.price - w2.price)
        len_w5 = abs(w5.price - w4.price)

        # Wave 3 is the shortest ONLY IF it's shorter than BOTH W1 and W5
        w3_is_shortest = (len_w3 < len_w1) and (len_w3 < len_w5)
        passes = not w3_is_shortest

        detail = (
            f"W1={len_w1:.4f}, W3={len_w3:.4f}, W5={len_w5:.4f}. "
            f"W3 is {'NOT ' if passes else ''}the shortest. "
            f"({'PASS' if passes else 'FAIL — W3 is shorter than both W1 and W5'})"
        )

        return RuleResult(
            rule_id="R2",
            rule_name="Wave 3 is never the shortest impulse wave",
            passed=passes,
            detail=detail,
            is_critical=True,
        )

    def _rule_3_wave4_no_w1_overlap(
        self,
        w1: Pivot,
        w4: Pivot,
        direction: Direction,
    ) -> tuple[RuleResult, bool]:
        """
        Rule 3: Wave 4 cannot enter Wave 1's price territory.
        For bullish: W4 bottom must stay ABOVE W1 top.
        For bearish: W4 top must stay BELOW W1 bottom.

        Returns (RuleResult, is_diagonal):
            is_diagonal = True when overlap is detected but count is otherwise
            valid. Diagonal triangles are a legitimate EW structure — we don't
            discard them, but we flag them and apply a score penalty.
        """
        if direction == "bullish":
            # W1 top = w1.price (it's a peak); W4 bottom = w4.price (it's a valley)
            overlap = w4.price < w1.price
            passes  = not overlap
            detail  = (
                f"W4_low={w4.price:.4f} {'>' if passes else '<'} W1_high={w1.price:.4f}. "
                f"({'PASS — no overlap' if passes else 'OVERLAP — possible diagonal'})"
            )
        else:
            # W1 bottom = w1.price (it's a valley); W4 top = w4.price (it's a peak)
            overlap = w4.price > w1.price
            passes  = not overlap
            detail  = (
                f"W4_high={w4.price:.4f} {'<' if passes else '>'} W1_low={w1.price:.4f}. "
                f"({'PASS — no overlap' if passes else 'OVERLAP — possible diagonal'})"
            )

        return RuleResult(
            rule_id="R3",
            rule_name="Wave 4 cannot enter Wave 1 territory",
            passed=passes,
            detail=detail,
            is_critical=not overlap,  # Critical ONLY if it's not a diagonal
        ), overlap  # overlap=True → treat as diagonal (not immediate discard)

    # ═══════════════════════════════════════════════════════════════════════
    #  GUIDELINES — violation reduces score, does NOT discard
    # ═══════════════════════════════════════════════════════════════════════

    def _guideline_w3_extends(self, w0, w1, w2, w3) -> GuidelineResult:
        """
        Guideline: Wave 3 often extends to 1.618× Wave 1 (the "golden ratio extension").
        Also acceptable: 1.0× (equal move) or 2.618× (full extension).
        """
        len_w1 = abs(w1.price - w0.price)
        len_w3 = abs(w3.price - w2.price)
        ratio  = len_w3 / len_w1 if len_w1 > 0 else 0.0

        ideal, dev = nearest_fibonacci(ratio, "extend")
        passes = dev <= FIBO_TOLERANCE * 2    # More lenient for guidelines
        score  = max(0.0, 1.0 - dev / (FIBO_TOLERANCE * 2)) if passes else 0.3

        return GuidelineResult(
            guideline_id="G1",
            guideline_name="Wave 3 extends via Fibonacci ratio of Wave 1",
            passed=passes,
            ratio=round(ratio, 4),
            ideal_ratio=ideal,
            deviation_pct=round(dev * 100, 2),
            score=round(score, 3),
        )

    def _guideline_w2_retrace(self, w0, w1, w2) -> GuidelineResult:
        """
        Guideline: Wave 2 typically retraces 50–78.6% of Wave 1.
        Deep retracements (61.8–78.6%) are most common.
        Shallow retracements (23.6–38.2%) also valid but less common.
        """
        len_w1    = abs(w1.price - w0.price)
        retrace   = abs(w2.price - w1.price)
        ratio     = retrace / len_w1 if len_w1 > 0 else 0.0

        ideal, dev = nearest_fibonacci(ratio, "retrace")
        passes = (0.382 <= ratio <= 0.886) and dev <= FIBO_TOLERANCE * 2
        score  = max(0.0, 1.0 - dev / (FIBO_TOLERANCE * 2)) if passes else 0.1

        return GuidelineResult(
            guideline_id="G2",
            guideline_name="Wave 2 retraces 38.2–88.6% of Wave 1",
            passed=passes,
            ratio=round(ratio, 4),
            ideal_ratio=ideal,
            deviation_pct=round(dev * 100, 2),
            score=round(score, 3),
        )

    def _guideline_w4_retrace(self, w2, w3, w4) -> GuidelineResult:
        """
        Guideline: Wave 4 typically retraces 23.6–50% of Wave 3.
        Wave 4 is shallower than Wave 2 (guideline of alternation).
        """
        len_w3  = abs(w3.price - w2.price)
        retrace = abs(w4.price - w3.price)
        ratio   = retrace / len_w3 if len_w3 > 0 else 0.0

        ideal, dev = nearest_fibonacci(ratio, "retrace")
        passes = (0.236 <= ratio <= 0.618) and dev <= FIBO_TOLERANCE * 2
        score  = max(0.0, 1.0 - dev / (FIBO_TOLERANCE * 2)) if passes else 0.1

        return GuidelineResult(
            guideline_id="G3",
            guideline_name="Wave 4 retraces 23.6–61.8% of Wave 3",
            passed=passes,
            ratio=round(ratio, 4),
            ideal_ratio=ideal,
            deviation_pct=round(dev * 100, 2),
            score=round(score, 3),
        )

    def _guideline_w5_equal_w1(self, w0, w1, w4, w5) -> GuidelineResult:
        """
        Guideline: When Wave 3 is extended, Wave 5 often equals Wave 1 in length.
        Also common: 0.618× or 1.618× of Wave 1.
        """
        len_w1 = abs(w1.price - w0.price)
        len_w5 = abs(w5.price - w4.price)
        ratio  = len_w5 / len_w1 if len_w1 > 0 else 0.0

        # W5 = W1 (ratio ~1.0), W5 = 0.618×W1, or W5 = 1.618×W1
        ideal, dev = nearest_fibonacci(ratio, "extend")
        passes = dev <= FIBO_TOLERANCE * 2
        score  = max(0.0, 1.0 - dev / (FIBO_TOLERANCE * 2)) if passes else 0.1

        return GuidelineResult(
            guideline_id="G4",
            guideline_name="Wave 5 relates to Wave 1 by Fibonacci",
            passed=passes,
            ratio=round(ratio, 4),
            ideal_ratio=ideal,
            deviation_pct=round(dev * 100, 2),
            score=round(score, 3),
        )

    def _guideline_alternation(self, w0, w1, w2, w3, w4) -> GuidelineResult:
        """
        Guideline of Alternation: Waves 2 and 4 tend to alternate in form.
        If W2 is a deep retrace → W4 tends to be shallow (and vice versa).
        Simple proxy: if W2_retrace_pct > 0.5, W4_retrace_pct should be < 0.5.
        """
        len_w1 = abs(w1.price - w0.price)
        len_w3 = abs(w3.price - w2.price)
        w2_retrace = abs(w2.price - w1.price) / len_w1 if len_w1 > 0 else 0
        w4_retrace = abs(w4.price - w3.price) / len_w3 if len_w3 > 0 else 0

        # True alternation: one deep, one shallow (separated by >0.2 in ratio)
        alternates = abs(w2_retrace - w4_retrace) > 0.2
        score = 1.0 if alternates else 0.3

        return GuidelineResult(
            guideline_id="G5",
            guideline_name="Waves 2 and 4 alternate in depth",
            passed=alternates,
            ratio=round(abs(w2_retrace - w4_retrace), 4),
            ideal_ratio=0.3,   # Ideal difference
            deviation_pct=round((1 - score) * 100, 2),
            score=round(score, 3),
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  STRUCTURE SCORE (0–20 pts)
    # ═══════════════════════════════════════════════════════════════════════

    def _compute_structure_score(self, guidelines: list[GuidelineResult]) -> int:
        """
        Compute the structure score (0–20) from guideline results.
        Guidelines have equal weight. Score = sum(scores) / count × 20.
        """
        if not guidelines:
            return 0
        avg_score = sum(g.score for g in guidelines) / len(guidelines)
        return round(avg_score * 20)

    # ═══════════════════════════════════════════════════════════════════════
    #  FIBONACCI SCORE (0–25 pts)
    # ═══════════════════════════════════════════════════════════════════════

    def _compute_fib_score(self, guidelines: list[GuidelineResult]) -> int:
        """
        Compute Fibonacci component score (0–25) from Fibonacci-based guidelines.
        Only G1–G4 are Fibonacci ratios; G5 (alternation) is structural.
        """
        fib_guidelines = [g for g in guidelines if g.guideline_id in ("G1","G2","G3","G4")]
        if not fib_guidelines:
            return 0
        avg_score = sum(g.score for g in fib_guidelines) / len(fib_guidelines)
        return round(avg_score * 25)

    # ═══════════════════════════════════════════════════════════════════════
    #  INVALIDATION LEVEL
    # ═══════════════════════════════════════════════════════════════════════

    def _compute_invalidation(self, pivots: list[Pivot], direction: Direction) -> float:
        """
        The price that mathematically disproves the current wave count.
        For any impulse/corrective count, this is the origin of the sequence (W0).
        W0 is the most conservative and mathematically unambiguous stop level:
        if price crosses W0, Rule 1 is definitionally violated for ANY sub-count.
        """
        if not pivots:
            return 0.0
        return pivots[0].price

    # ═══════════════════════════════════════════════════════════════════════
    #  CURRENT WAVE CLASSIFIER
    # ═══════════════════════════════════════════════════════════════════════

    def _classify_current_wave(
        self,
        pivots: list[Pivot],
        pattern_type: PatternType,
    ) -> str:
        """
        Determine which wave the market is currently in based on the last pivot.
        This is used by the MTF State Machine as the Macro context descriptor.

        For a 6-pivot impulse [W0,W1,W2,W3,W4,W5]:
            Last pivot is W5 → currently in Wave 5 (or just completed it)
        For a 4-pivot corrective [A_start, A_end, B_end, C_end]:
            Last pivot is C_end → currently in Wave C
        """
        if not pivots:
            return "unknown"

        last = pivots[-1]

        if pattern_type in ("impulse", "diagonal_ending", "diagonal_leading"):
            # Map pivot position to wave label
            label_map = {0: "0", 1: "1", 2: "2", 3: "3", 4: "4", 5: "5"}
            idx = len(pivots) - 1
            return label_map.get(idx, str(idx))

        elif pattern_type in ("corrective_abc", "zigzag"):
            label_map = {0: "A_start", 1: "A", 2: "B", 3: "C"}
            idx = len(pivots) - 1
            return label_map.get(idx, str(idx))

        return "unknown"

    # ═══════════════════════════════════════════════════════════════════════
    #  PUBLIC API: validate_impulse
    # ═══════════════════════════════════════════════════════════════════════

    def validate_impulse(self, pivots: list[Pivot]) -> ElliottGuardResult:
        """
        Validate a 6-pivot sequence as an Elliott Wave 5-wave impulse.

        Expects exactly 6 pivots: [W0, W1, W2, W3, W4, W5]
        W0 = start (valley for bullish / peak for bearish)
        W1 = end of Wave 1
        W2 = end of Wave 2 (retracement)
        W3 = end of Wave 3 (extension)
        W4 = end of Wave 4 (retracement)
        W5 = end of Wave 5 (final push)

        Returns ElliottGuardResult with valid=True ONLY if all 3 rules pass.
        """
        if len(pivots) != 6:
            return ElliottGuardResult(
                valid=False,
                pattern_type="impulse",
                direction="bullish",
                reject_reason=f"Impulse requires exactly 6 pivots, got {len(pivots)}.",
            )

        w0, w1, w2, w3, w4, w5 = pivots

        direction = _classify_direction(pivots)
        log.debug(f"[ElliottGuard] validate_impulse: {direction}, pivots: "
                  f"[{w0.price:.2f}, {w1.price:.2f}, {w2.price:.2f}, "
                  f"{w3.price:.2f}, {w4.price:.2f}, {w5.price:.2f}]")

        # ── Structural sanity check ─────────────────────────────────────────
        # For bullish: pattern must be valley → peak → valley → peak → valley → peak
        # For bearish: pattern must be peak → valley → peak → valley → peak → valley
        expected_types = (
            ["valley","peak","valley","peak","valley","peak"]
            if direction == "bullish"
            else ["peak","valley","peak","valley","peak","valley"]
        )
        actual_types = [p.pivot_type for p in pivots]
        if actual_types != expected_types:
            return ElliottGuardResult(
                valid=False,
                pattern_type="impulse",
                direction=direction,
                reject_reason=(
                    f"Pivot type sequence invalid for {direction} impulse. "
                    f"Expected {expected_types}, got {actual_types}."
                ),
                pivots=pivots,
            )

        # ── Run 3 inviolable rules ──────────────────────────────────────────
        r1 = self._rule_1_wave2_no_full_retrace(w0, w1, w2, direction)
        r2 = self._rule_2_wave3_not_shortest(w0, w1, w2, w3, w4, w5)
        r3, is_diagonal = self._rule_3_wave4_no_w1_overlap(w1, w4, direction)

        rules = [r1, r2, r3]

        # ── Fail-fast on critical rule violations ───────────────────────────
        for rule in rules:
            if not rule.passed and rule.is_critical:
                log.debug(f"[ElliottGuard] DISCARD: {rule.rule_id} failed — {rule.detail}")
                return ElliottGuardResult(
                    valid=False,
                    pattern_type="diagonal_ending" if is_diagonal else "impulse",
                    direction=direction,
                    rules=rules,
                    is_diagonal=is_diagonal,
                    reject_reason=f"{rule.rule_id} violation: {rule.detail}",
                    pivots=pivots,
                )

        # ── All rules pass (or diagonal override) ───────────────────────────
        pattern_type: PatternType = "diagonal_ending" if is_diagonal else "impulse"
        rules_score = 40 if not is_diagonal else 25  # Diagonal penalty

        # ── Run guidelines ──────────────────────────────────────────────────
        guidelines = [
            self._guideline_w3_extends(w0, w1, w2, w3),
            self._guideline_w2_retrace(w0, w1, w2),
            self._guideline_w4_retrace(w2, w3, w4),
            self._guideline_w5_equal_w1(w0, w1, w4, w5),
            self._guideline_alternation(w0, w1, w2, w3, w4),
        ]

        structure_score = self._compute_structure_score(guidelines)
        fib_score       = self._compute_fib_score(guidelines)

        # Apply diagonal penalty to structure score
        if is_diagonal:
            structure_score = round(structure_score * 0.7)

        current_wave  = self._classify_current_wave(pivots, pattern_type)
        invalidation  = self._compute_invalidation(pivots, direction)
        base_score    = rules_score + structure_score

        log.info(
            f"[ElliottGuard] VALID {direction} {pattern_type}: "
            f"rules={rules_score} struct={structure_score} fib={fib_score} "
            f"base={base_score} current_wave={current_wave}"
        )

        return ElliottGuardResult(
            valid=True,
            pattern_type=pattern_type,
            direction=direction,
            rules=rules,
            guidelines=guidelines,
            rules_score=rules_score,
            structure_score=structure_score,
            fib_score=fib_score,
            is_diagonal=is_diagonal,
            current_wave=current_wave,
            invalidation=invalidation,
            base_score=base_score,
            pivots=pivots,
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  PUBLIC API: validate_corrective
    # ═══════════════════════════════════════════════════════════════════════

    def validate_corrective(self, pivots: list[Pivot]) -> ElliottGuardResult:
        """
        Validate a 4-pivot sequence as an A-B-C corrective pattern.

        Expects exactly 4 pivots: [Origin, A_end, B_end, C_end]
        Origin = start of the correction
        A_end  = end of A wave (impulse in correction direction)
        B_end  = end of B wave (retracement, relief rally/selloff)
        C_end  = end of C wave (resumption of correction direction)

        Rules for ABC:
          1. B cannot retrace beyond the start (Origin) of the correction
          2. C must move beyond A_end in the correction direction (C > A in length)
             Exception: flat corrections where C ≈ A

        Returns ElliottGuardResult with valid=True only if rules pass.
        """
        if len(pivots) != 4:
            return ElliottGuardResult(
                valid=False,
                pattern_type="corrective_abc",
                direction="bearish",
                reject_reason=f"ABC corrective requires exactly 4 pivots, got {len(pivots)}.",
            )

        origin, a_end, b_end, c_end = pivots
        direction = _classify_direction([origin, a_end])

        log.debug(
            f"[ElliottGuard] validate_corrective: {direction} ABC, pivots: "
            f"[{origin.price:.2f}, {a_end.price:.2f}, {b_end.price:.2f}, {c_end.price:.2f}]"
        )

        rules: list[RuleResult] = []

        # ── ABC Rule 1: B cannot exceed origin ──────────────────────────────
        if direction == "bearish":  # Bearish correction: A goes down
            b_exceeds_origin = b_end.price > origin.price
        else:  # Bullish correction: A goes up
            b_exceeds_origin = b_end.price < origin.price

        r_b = RuleResult(
            rule_id="ABC-R1",
            rule_name="B wave cannot exceed origin of correction",
            passed=not b_exceeds_origin,
            detail=(
                f"B={b_end.price:.4f} {'exceeds' if b_exceeds_origin else 'respects'} "
                f"origin={origin.price:.4f}. "
                f"({'FAIL' if b_exceeds_origin else 'PASS'})"
            ),
            is_critical=True,
        )
        rules.append(r_b)

        if b_exceeds_origin:
            return ElliottGuardResult(
                valid=False,
                pattern_type="corrective_abc",
                direction=direction,
                rules=rules,
                reject_reason=f"ABC-R1 violation: {r_b.detail}",
                pivots=pivots,
            )

        # ── ABC Rule 2: C must be impulsive (at least 0.618× A length) ──────
        len_a = abs(a_end.price - origin.price)
        len_c = abs(c_end.price - b_end.price)
        c_to_a_ratio = len_c / len_a if len_a > 0 else 0.0

        # Flat: C ≈ A (ratio ~0.9–1.1)
        # Zigzag: C ≥ A (ratio ≥ 1.0)
        # Minimum: C must be at least 0.618× A (truncated C — rare but valid)
        c_is_valid = c_to_a_ratio >= 0.618

        r_c = RuleResult(
            rule_id="ABC-R2",
            rule_name="C wave must be at least 0.618× length of A wave",
            passed=c_is_valid,
            detail=(
                f"C/A ratio={c_to_a_ratio:.3f}. "
                f"({'PASS' if c_is_valid else f'FAIL — C too short relative to A'})"
            ),
            is_critical=True,
        )
        rules.append(r_c)

        if not c_is_valid:
            return ElliottGuardResult(
                valid=False,
                pattern_type="corrective_abc",
                direction=direction,
                rules=rules,
                reject_reason=f"ABC-R2 violation: {r_c.detail}",
                pivots=pivots,
            )

        # ── Classify ABC sub-type ────────────────────────────────────────────
        # Zigzag:  C > A  (c_to_a > 1.0)
        # Flat:    C ≈ A  (c_to_a 0.9–1.1)
        # Expanded: C > A and B > A start (already blocked by R1 — so rare here)
        if 0.9 <= c_to_a_ratio <= 1.1:
            pattern_type: PatternType = "flat"
        else:
            pattern_type = "zigzag"

        rules_score = 40  # All ABC rules passed

        # ── ABC Fibonacci guidelines ─────────────────────────────────────────
        # B retraces A: typically 50–78.6%
        len_a_leg = abs(a_end.price - origin.price)
        b_retrace = abs(b_end.price - a_end.price)
        b_ratio   = b_retrace / len_a_leg if len_a_leg > 0 else 0
        b_ideal, b_dev = nearest_fibonacci(b_ratio, "retrace")
        b_gl = GuidelineResult(
            guideline_id="ABC-G1",
            guideline_name="B wave retraces 38.2–88.6% of A wave",
            passed=0.382 <= b_ratio <= 0.886,
            ratio=round(b_ratio, 4),
            ideal_ratio=b_ideal,
            deviation_pct=round(b_dev * 100, 2),
            score=max(0.0, 1.0 - b_dev / (FIBO_TOLERANCE * 2)),
        )

        # C extends from B: typically 1.0× or 1.618× of A
        c_ideal, c_dev = nearest_fibonacci(c_to_a_ratio, "extend")
        c_gl = GuidelineResult(
            guideline_id="ABC-G2",
            guideline_name="C wave extends 1.0–1.618× of A wave",
            passed=c_dev <= FIBO_TOLERANCE * 2,
            ratio=round(c_to_a_ratio, 4),
            ideal_ratio=c_ideal,
            deviation_pct=round(c_dev * 100, 2),
            score=max(0.0, 1.0 - c_dev / (FIBO_TOLERANCE * 2)),
        )

        guidelines = [b_gl, c_gl]
        structure_score = self._compute_structure_score(guidelines)
        fib_score       = round((b_gl.score + c_gl.score) / 2 * 25)

        current_wave  = self._classify_current_wave(pivots, pattern_type)
        invalidation  = self._compute_invalidation(pivots, direction)
        base_score    = rules_score + structure_score

        log.info(
            f"[ElliottGuard] VALID {direction} {pattern_type}: "
            f"rules={rules_score} struct={structure_score} fib={fib_score} "
            f"base={base_score} current_wave={current_wave}"
        )

        return ElliottGuardResult(
            valid=True,
            pattern_type=pattern_type,
            direction=direction,
            rules=rules,
            guidelines=guidelines,
            rules_score=rules_score,
            structure_score=structure_score,
            fib_score=fib_score,
            is_diagonal=False,
            current_wave=current_wave,
            invalidation=invalidation,
            base_score=base_score,
            pivots=pivots,
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  BATCH VALIDATION (for pivot window candidates)
    # ═══════════════════════════════════════════════════════════════════════

    def validate_all_candidates(
        self,
        impulse_candidates:    list[list[Pivot]],
        corrective_candidates: list[list[Pivot]],
        max_results:           int = 5,
    ) -> list[ElliottGuardResult]:
        """
        Validate all candidate pivot windows (impulse + corrective).
        Returns only VALID results, sorted by base_score descending.
        Limits to max_results to prevent downstream processing explosion.

        This is the primary entry point called by the orchestrator.
        It receives all sliding windows from extract_wave_candidates()
        and returns the best valid wave counts for MTF filtering.
        """
        valid_results: list[ElliottGuardResult] = []

        # Validate impulse candidates (6-pivot windows)
        for candidate in impulse_candidates:
            result = self.validate_impulse(candidate)
            if result.valid:
                valid_results.append(result)
                if len(valid_results) >= max_results * 2:  # Collect extra, trim later
                    break

        # Validate corrective candidates (4-pivot windows)
        for candidate in corrective_candidates:
            result = self.validate_corrective(candidate)
            if result.valid:
                valid_results.append(result)
                if len(valid_results) >= max_results * 3:
                    break

        # Sort by base_score descending, return top max_results
        valid_results.sort(key=lambda r: r.base_score, reverse=True)
        return valid_results[:max_results]
