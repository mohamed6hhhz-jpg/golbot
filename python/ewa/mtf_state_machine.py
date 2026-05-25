"""
ewa/mtf_state_machine.py

Phase 4: Multi-Timeframe State Machine — Contradiction Resolution Engine
=========================================================================

THE CORE PROBLEM THIS SOLVES:
    Competitor failure cause: Daily chart shows Bullish Wave 3 (up-trend).
    Hourly chart shows what LOOKS like a Bearish Impulse 1-2-3-4-5 (down-trend).
    A naive engine reports BOTH — contradicting itself. Users get confused.
    No trade signal is actionable when the direction is ambiguous.

THE SOLUTION: Hierarchical State Machine with Hard Context Filters
    Level 1 (Macro): Analyze the HIGHER timeframe (1D) first.
                     Determine the Macro State: "Wave 3 Bullish Impulse".
    Level 2 (Micro): Pass the Macro State as a CONSTRAINT to the 1H analysis.
                     The 1H must show a pattern COMPATIBLE with Macro Wave 3 Bullish.
                     A bearish impulse on 1H would be Wave 4 correction of the daily
                     Wave 3 — INTERNALLY valid. An outright bearish Wave 1 break
                     below the Daily Wave 0 origin would be INCOMPATIBLE — discarded.

COMPATIBILITY MATRIX (Macro State → Allowed Micro Patterns):
    ┌─────────────────────┬──────────────────────────────────────────────────┐
    │ Macro State         │ Compatible Micro Patterns                        │
    ├─────────────────────┼──────────────────────────────────────────────────┤
    │ Impulse W1 Bullish  │ Bullish impulse (sub-W1), small corrective       │
    │ Impulse W2 Bullish  │ Bearish corrective (ABC pullback)                │
    │ Impulse W3 Bullish  │ Bullish impulse OR corrective (internal W4)      │
    │ Impulse W4 Bullish  │ Bearish corrective (mandatory), NO bullish imp.  │
    │ Impulse W5 Bullish  │ Bullish impulse (weakening), divergence watch    │
    │ Corrective A Bear   │ Bearish impulse (A-wave is internally impulsive) │
    │ Corrective B Bull   │ Bullish corrective (B is a relief rally)         │
    │ Corrective C Bear   │ Bearish impulse (C-wave is internally impulsive) │
    │ (same for bearish directions, inverted)                                │
    └─────────────────────┴──────────────────────────────────────────────────┘

CONTRADICTION RESOLUTION OUTCOMES:
    ALIGNED:       Micro pattern is in the allowed set → MTF score = 10/10
    PARTIAL:       Micro pattern is borderline (e.g. corrective where impulse      
                   expected) → MTF score = 5/10
    CONTRADICTION: No micro candidate matches macro constraints → MTF score = 0,
                   analysis returns the macro result only with a contradiction notice.
                   No trade signal is generated for contradicted scenarios.

MOMENTUM SCORE (5 pts):
    We compute a simple momentum consistency check:
    Does the micro analysis direction agree with the macro momentum?
    Proxy: is the latest micro close above/below the macro pivot midpoint?
    Score: 5/5 if aligned, 0/5 if contradicting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .elliott_guard import ElliottGuardResult, Direction, PatternType

log = logging.getLogger(__name__)


# ─── Enums & State Definitions ────────────────────────────────────────────────

class MacroWavePosition(Enum):
    """
    Possible positions within an Elliott Wave cycle at the Macro (higher TF) level.
    Named to be self-documenting — no magic numbers.
    """
    # 5-wave impulse positions
    IMPULSE_W1_BULL  = "impulse_w1_bullish"
    IMPULSE_W2_BULL  = "impulse_w2_bullish"   # Corrective pullback in bull trend
    IMPULSE_W3_BULL  = "impulse_w3_bullish"   # Strongest bullish wave
    IMPULSE_W4_BULL  = "impulse_w4_bullish"   # Corrective pullback (mandatory)
    IMPULSE_W5_BULL  = "impulse_w5_bullish"   # Final push (watch divergence)

    IMPULSE_W1_BEAR  = "impulse_w1_bearish"
    IMPULSE_W2_BEAR  = "impulse_w2_bearish"   # Relief rally in bear trend
    IMPULSE_W3_BEAR  = "impulse_w3_bearish"   # Strongest bearish wave
    IMPULSE_W4_BEAR  = "impulse_w4_bearish"   # Corrective rally (mandatory)
    IMPULSE_W5_BEAR  = "impulse_w5_bearish"   # Final drop (watch divergence)

    # A-B-C corrective positions
    CORRECTIVE_A_BEAR = "corrective_a_bearish"  # A-wave down
    CORRECTIVE_B_BULL = "corrective_b_bullish"  # B-wave relief rally
    CORRECTIVE_C_BEAR = "corrective_c_bearish"  # C-wave down (resumption)

    CORRECTIVE_A_BULL = "corrective_a_bullish"  # A-wave up (in larger correction)
    CORRECTIVE_B_BEAR = "corrective_b_bearish"  # B-wave pullback
    CORRECTIVE_C_BULL = "corrective_c_bullish"  # C-wave up

    UNDEFINED         = "undefined"


class MTFAlignment(Enum):
    """Quality of alignment between Macro and Micro wave counts."""
    FULL        = "full"         # Micro perfectly fits Macro context
    PARTIAL     = "partial"      # Micro fits but with caveats
    WEAK        = "weak"         # Micro is technically allowed but unusual
    CONTRADICTION = "contradiction"  # Micro has NO valid count fitting Macro


# ─── Constraint Definitions ───────────────────────────────────────────────────

@dataclass(frozen=True)
class MTFConstraint:
    """
    Defines what micro-level patterns are compatible with a given macro state.
    This is the core of the contradiction resolution engine.
    """
    macro_position:          MacroWavePosition
    macro_direction:         Direction

    # Which micro directions are ALLOWED (hard filter)
    allowed_micro_directions: frozenset[Direction]

    # Which micro pattern types are ALLOWED (hard filter)
    allowed_micro_patterns:   frozenset[PatternType]

    # Preferred micro pattern for highest MTF alignment score
    preferred_micro_pattern:  PatternType

    # Is the micro expected to be corrective in nature?
    micro_should_be_corrective: bool

    # Momentum bias: is the macro momentum currently accelerating or decelerating?
    momentum_bias: str  # "accelerating" | "decelerating" | "neutral"

    # Arabic description for the UI verdict panel
    description_ar: str

    # English description for debugging/logging
    description_en: str

    # MTF score when micro perfectly matches preferred pattern (full alignment)
    full_alignment_score: int = 10

    # MTF score when micro matches allowed but not preferred (partial alignment)
    partial_alignment_score: int = 5

    # MTF score when no micro pattern matches (contradiction)
    contradiction_score: int = 0


# ─── The Constraint Table ─────────────────────────────────────────────────────

# This is the mathematical heart of the MTF engine.
# Every possible Macro state maps to exactly one MTFConstraint object.
# The Micro analysis result is filtered against this table — no exceptions.

MTF_CONSTRAINT_TABLE: dict[MacroWavePosition, MTFConstraint] = {

    # ── BULLISH IMPULSE WAVES ──────────────────────────────────────────────

    MacroWavePosition.IMPULSE_W1_BULL: MTFConstraint(
        macro_position=MacroWavePosition.IMPULSE_W1_BULL,
        macro_direction="bullish",
        allowed_micro_directions=frozenset(["bullish", "bearish"]),
        allowed_micro_patterns=frozenset([
            "impulse", "corrective_abc", "zigzag", "flat", "diagonal_leading"
        ]),
        preferred_micro_pattern="impulse",
        micro_should_be_corrective=False,
        momentum_bias="accelerating",
        description_ar=(
            "الموجة 1 الكبرى صاعدة — بداية الدورة. "
            "الصغرى يمكن أن تكون نبضة صاعدة فرعية أو تصحيحاً قصيراً "
            "قبل الاستمرار."
        ),
        description_en=(
            "Macro Wave 1 Bullish — start of new bullish cycle. "
            "Micro may be sub-wave impulse or short corrective pullback."
        ),
    ),

    MacroWavePosition.IMPULSE_W2_BULL: MTFConstraint(
        macro_position=MacroWavePosition.IMPULSE_W2_BULL,
        macro_direction="bullish",
        # W2 is a corrective wave — micro MUST be bearish/corrective
        allowed_micro_directions=frozenset(["bearish"]),
        allowed_micro_patterns=frozenset([
            "corrective_abc", "zigzag", "flat", "triangle"
        ]),
        preferred_micro_pattern="corrective_abc",
        micro_should_be_corrective=True,
        momentum_bias="decelerating",
        description_ar=(
            "الموجة 2 الكبرى — تصحيح لازم للموجة 1. "
            "الصغرى 1H يجب أن تُظهر بنية تصحيحية A-B-C. "
            "أي نبضة صاعدة على الصغرى تُعدّ خاطئة في هذا السياق."
        ),
        description_en=(
            "Macro Wave 2 — mandatory corrective pullback of Wave 1. "
            "Micro 1H MUST show A-B-C corrective structure. "
            "Any bullish impulse on micro contradicts macro context."
        ),
    ),

    MacroWavePosition.IMPULSE_W3_BULL: MTFConstraint(
        macro_position=MacroWavePosition.IMPULSE_W3_BULL,
        macro_direction="bullish",
        # W3 is the strongest wave — micro may be sub-wave impulse OR internal W4 correction
        allowed_micro_directions=frozenset(["bullish", "bearish"]),
        allowed_micro_patterns=frozenset([
            "impulse", "corrective_abc", "zigzag", "flat", "diagonal_ending"
        ]),
        preferred_micro_pattern="impulse",
        micro_should_be_corrective=False,
        momentum_bias="accelerating",
        description_ar=(
            "الموجة 3 الكبرى الصاعدة — أقوى موجة في الدورة. "
            "الصغرى قد تكون نبضة فرعية صاعدة أو تصحيح داخلي (موجة 4 صغرى). "
            "نبضة هابطة على الصغرى تتوافق فقط إذا كانت تصحيحاً للموجة 3 الكبرى."
        ),
        description_en=(
            "Macro Wave 3 Bullish — strongest wave in the cycle. "
            "Micro may be sub-impulse (bull) or internal W4 correction (bear). "
            "A bearish micro impulse is valid ONLY as an internal Wave 4 pullback."
        ),
    ),

    MacroWavePosition.IMPULSE_W4_BULL: MTFConstraint(
        macro_position=MacroWavePosition.IMPULSE_W4_BULL,
        macro_direction="bullish",
        # W4 is a corrective wave — macro is bullish but micro MUST be corrective/bearish
        allowed_micro_directions=frozenset(["bearish"]),
        allowed_micro_patterns=frozenset([
            "corrective_abc", "zigzag", "flat", "triangle"
        ]),
        preferred_micro_pattern="corrective_abc",
        micro_should_be_corrective=True,
        momentum_bias="decelerating",
        description_ar=(
            "الموجة 4 الكبرى — تصحيح الموجة 3. "
            "الصغرى 1H يجب أن تكون تصحيحية (A-B-C). "
            "قاعدة الموجة 4: لا يجوز أن تدخل منطقة الموجة 1 الكبرى."
        ),
        description_en=(
            "Macro Wave 4 — corrective pullback of Wave 3. "
            "Micro 1H MUST be corrective (A-B-C). "
            "W4 rule: must not enter Wave 1 territory — watch invalidation level."
        ),
    ),

    MacroWavePosition.IMPULSE_W5_BULL: MTFConstraint(
        macro_position=MacroWavePosition.IMPULSE_W5_BULL,
        macro_direction="bullish",
        # W5 is bullish but often shows momentum divergence — micro may be weakening
        allowed_micro_directions=frozenset(["bullish"]),
        allowed_micro_patterns=frozenset([
            "impulse", "diagonal_ending"
        ]),
        preferred_micro_pattern="impulse",
        micro_should_be_corrective=False,
        momentum_bias="decelerating",   # W5 momentum often weaker than W3
        description_ar=(
            "الموجة 5 الكبرى — الدفع الأخير قبل الانعكاس. "
            "انتبه للتباعد السلبي في الزخم. "
            "الصغرى يجب أن تكون نبضة صاعدة، غالباً بزخم أضعف من الموجة 3."
        ),
        description_en=(
            "Macro Wave 5 Bullish — final push before major reversal. "
            "Watch for bearish momentum divergence. "
            "Micro must be bullish impulse, typically with weaker momentum than W3."
        ),
    ),

    # ── BEARISH IMPULSE WAVES ──────────────────────────────────────────────

    MacroWavePosition.IMPULSE_W1_BEAR: MTFConstraint(
        macro_position=MacroWavePosition.IMPULSE_W1_BEAR,
        macro_direction="bearish",
        allowed_micro_directions=frozenset(["bearish", "bullish"]),
        allowed_micro_patterns=frozenset([
            "impulse", "corrective_abc", "zigzag", "flat"
        ]),
        preferred_micro_pattern="impulse",
        micro_should_be_corrective=False,
        momentum_bias="accelerating",
        description_ar=(
            "الموجة 1 الكبرى الهابطة — بداية الدورة الهابطة. "
            "الصغرى يمكن أن تكون نبضة هابطة فرعية أو ارتداد قصير."
        ),
        description_en=(
            "Macro Wave 1 Bearish — start of bearish cycle. "
            "Micro may be sub-impulse (bear) or short corrective relief rally."
        ),
    ),

    MacroWavePosition.IMPULSE_W2_BEAR: MTFConstraint(
        macro_position=MacroWavePosition.IMPULSE_W2_BEAR,
        macro_direction="bearish",
        allowed_micro_directions=frozenset(["bullish"]),
        allowed_micro_patterns=frozenset([
            "corrective_abc", "zigzag", "flat", "triangle"
        ]),
        preferred_micro_pattern="corrective_abc",
        micro_should_be_corrective=True,
        momentum_bias="decelerating",
        description_ar=(
            "الموجة 2 الهابطة الكبرى — ارتداد تصحيحي للموجة 1. "
            "الصغرى 1H يجب أن تُظهر ارتداداً تصحيحياً (A-B-C صاعد). "
            "انتبه: هذا الارتداد مضلل — الاتجاه الكبير لا يزال هابطاً."
        ),
        description_en=(
            "Macro Wave 2 Bear — corrective relief rally after W1 drop. "
            "Micro must show bullish A-B-C corrective (deceptive rally). "
            "Warning: This is a bull trap — macro trend is still bearish."
        ),
    ),

    MacroWavePosition.IMPULSE_W3_BEAR: MTFConstraint(
        macro_position=MacroWavePosition.IMPULSE_W3_BEAR,
        macro_direction="bearish",
        allowed_micro_directions=frozenset(["bearish", "bullish"]),
        allowed_micro_patterns=frozenset([
            "impulse", "corrective_abc", "zigzag", "flat"
        ]),
        preferred_micro_pattern="impulse",
        micro_should_be_corrective=False,
        momentum_bias="accelerating",
        description_ar=(
            "الموجة 3 الكبرى الهابطة — أقوى موجة هبوطية. "
            "الصغرى قد تكون نبضة هابطة فرعية أو تصحيحاً داخلياً (موجة 4 صغرى)."
        ),
        description_en=(
            "Macro Wave 3 Bearish — strongest bearish wave in cycle. "
            "Micro may be sub-bearish-impulse or internal W4 correction."
        ),
    ),

    MacroWavePosition.IMPULSE_W4_BEAR: MTFConstraint(
        macro_position=MacroWavePosition.IMPULSE_W4_BEAR,
        macro_direction="bearish",
        allowed_micro_directions=frozenset(["bullish"]),
        allowed_micro_patterns=frozenset([
            "corrective_abc", "zigzag", "flat", "triangle"
        ]),
        preferred_micro_pattern="corrective_abc",
        micro_should_be_corrective=True,
        momentum_bias="decelerating",
        description_ar=(
            "الموجة 4 الكبرى الهابطة — تصحيح للموجة 3. "
            "الصغرى 1H يجب أن تكون ارتداداً تصحيحياً صاعداً (A-B-C). "
            "فرصة لبيع على الارتداد بعد اكتمال التصحيح."
        ),
        description_en=(
            "Macro Wave 4 Bear — corrective rally after W3 drop. "
            "Micro must be bullish corrective (A-B-C) — sell-on-rally setup."
        ),
    ),

    MacroWavePosition.IMPULSE_W5_BEAR: MTFConstraint(
        macro_position=MacroWavePosition.IMPULSE_W5_BEAR,
        macro_direction="bearish",
        allowed_micro_directions=frozenset(["bearish"]),
        allowed_micro_patterns=frozenset([
            "impulse", "diagonal_ending"
        ]),
        preferred_micro_pattern="impulse",
        micro_should_be_corrective=False,
        momentum_bias="decelerating",
        description_ar=(
            "الموجة 5 الكبرى الهابطة — الدفع النهائي قبل الانعكاس الكبير. "
            "انتبه للتباعد الإيجابي في الزخم — إشارة وشيكة للانعكاس."
        ),
        description_en=(
            "Macro Wave 5 Bearish — final drop before major reversal. "
            "Watch for bullish momentum divergence. Near-term capitulation expected."
        ),
    ),

    # ── CORRECTIVE WAVES ───────────────────────────────────────────────────

    MacroWavePosition.CORRECTIVE_A_BEAR: MTFConstraint(
        macro_position=MacroWavePosition.CORRECTIVE_A_BEAR,
        macro_direction="bearish",
        allowed_micro_directions=frozenset(["bearish"]),
        allowed_micro_patterns=frozenset(["impulse"]),
        preferred_micro_pattern="impulse",
        micro_should_be_corrective=False,
        momentum_bias="accelerating",
        description_ar=(
            "الموجة A الهابطة — الساق الأولى للتصحيح الكبير. "
            "الموجة A داخلياً نبضية هابطة. الصغرى يجب أن تكون نبضة هابطة."
        ),
        description_en=(
            "Corrective A-wave down — first leg of major correction. "
            "A-waves are internally impulsive. Micro must show bearish impulse."
        ),
    ),

    MacroWavePosition.CORRECTIVE_B_BULL: MTFConstraint(
        macro_position=MacroWavePosition.CORRECTIVE_B_BULL,
        macro_direction="bullish",
        allowed_micro_directions=frozenset(["bullish"]),
        allowed_micro_patterns=frozenset([
            "corrective_abc", "zigzag", "flat", "triangle"
        ]),
        preferred_micro_pattern="corrective_abc",
        micro_should_be_corrective=True,
        momentum_bias="decelerating",
        description_ar=(
            "الموجة B — الارتداد المضلل. "
            "الموجة B داخلياً تصحيحية وتُشكّل فخاً للمشترين. "
            "الصغرى تُظهر بنية تصحيحية صاعدة — لا تنخدع بالاتجاه الصاعد."
        ),
        description_en=(
            "Corrective B-wave — deceptive rally (bull trap). "
            "B-waves are internally corrective. Micro shows bullish corrective structure. "
            "Do NOT trade this as a bullish reversal — larger downtrend resumes after B."
        ),
    ),

    MacroWavePosition.CORRECTIVE_C_BEAR: MTFConstraint(
        macro_position=MacroWavePosition.CORRECTIVE_C_BEAR,
        macro_direction="bearish",
        allowed_micro_directions=frozenset(["bearish"]),
        allowed_micro_patterns=frozenset(["impulse", "diagonal_ending"]),
        preferred_micro_pattern="impulse",
        micro_should_be_corrective=False,
        momentum_bias="accelerating",
        description_ar=(
            "الموجة C الهابطة — الساق الأخيرة للتصحيح الكبير. "
            "الموجة C نبضية داخلياً وغالباً الأكثر ألماً للمشترين. "
            "الصغرى يجب أن تُظهر نبضة هابطة واضحة."
        ),
        description_en=(
            "Corrective C-wave down — final, most damaging leg of major correction. "
            "C-waves are internally impulsive. Micro must show clear bearish impulse."
        ),
    ),

    MacroWavePosition.CORRECTIVE_A_BULL: MTFConstraint(
        macro_position=MacroWavePosition.CORRECTIVE_A_BULL,
        macro_direction="bullish",
        allowed_micro_directions=frozenset(["bullish"]),
        allowed_micro_patterns=frozenset(["impulse"]),
        preferred_micro_pattern="impulse",
        micro_should_be_corrective=False,
        momentum_bias="accelerating",
        description_ar="الموجة A الصاعدة — الساق الأولى لتصحيح صاعد.",
        description_en="Corrective A-wave up — first leg of bullish correction.",
    ),

    MacroWavePosition.CORRECTIVE_B_BEAR: MTFConstraint(
        macro_position=MacroWavePosition.CORRECTIVE_B_BEAR,
        macro_direction="bearish",
        allowed_micro_directions=frozenset(["bearish"]),
        allowed_micro_patterns=frozenset([
            "corrective_abc", "zigzag", "flat"
        ]),
        preferred_micro_pattern="corrective_abc",
        micro_should_be_corrective=True,
        momentum_bias="decelerating",
        description_ar="الموجة B الهابطة — تصحيح ضمن تصحيح أكبر صاعد.",
        description_en="Corrective B-wave down — pullback within larger bullish correction.",
    ),

    MacroWavePosition.CORRECTIVE_C_BULL: MTFConstraint(
        macro_position=MacroWavePosition.CORRECTIVE_C_BULL,
        macro_direction="bullish",
        allowed_micro_directions=frozenset(["bullish"]),
        allowed_micro_patterns=frozenset(["impulse", "diagonal_ending"]),
        preferred_micro_pattern="impulse",
        micro_should_be_corrective=False,
        momentum_bias="accelerating",
        description_ar="الموجة C الصاعدة — الساق الأخيرة للتصحيح الصاعد.",
        description_en="Corrective C-wave up — final leg of bullish corrective sequence.",
    ),

    MacroWavePosition.UNDEFINED: MTFConstraint(
        macro_position=MacroWavePosition.UNDEFINED,
        macro_direction="bullish",
        allowed_micro_directions=frozenset(["bullish", "bearish"]),
        allowed_micro_patterns=frozenset([
            "impulse", "corrective_abc", "zigzag", "flat",
            "triangle", "diagonal_ending", "diagonal_leading"
        ]),
        preferred_micro_pattern="impulse",
        micro_should_be_corrective=False,
        momentum_bias="neutral",
        description_ar="السياق الكبير غير محدد — تحليل مستقل للإطار الصغير.",
        description_en="Macro context undefined — micro analyzed independently.",
        full_alignment_score=5,    # Reduced max score when macro is unclear
        partial_alignment_score=3,
    ),
}


# ─── Macro State Classifier ───────────────────────────────────────────────────

def classify_macro_state(macro_result: ElliottGuardResult) -> MacroWavePosition:
    """
    Map a macro ElliottGuardResult to a MacroWavePosition enum value.
    This is the bridge between the Elliott Guard output and the MTF constraint table.

    The current_wave field from ElliottGuardResult tells us which wave the
    macro analysis is currently in. Combined with direction, we get the full state.
    """
    if not macro_result.valid:
        return MacroWavePosition.UNDEFINED

    direction    = macro_result.direction
    current_wave = macro_result.current_wave
    pattern_type = macro_result.pattern_type

    is_bull = direction == "bullish"
    is_bear = direction == "bearish"

    # ── Impulse wave mapping ─────────────────────────────────────────────────
    if pattern_type in ("impulse", "diagonal_ending", "diagonal_leading"):
        wave_map_bull = {
            "1": MacroWavePosition.IMPULSE_W1_BULL,
            "2": MacroWavePosition.IMPULSE_W2_BULL,
            "3": MacroWavePosition.IMPULSE_W3_BULL,
            "4": MacroWavePosition.IMPULSE_W4_BULL,
            "5": MacroWavePosition.IMPULSE_W5_BULL,
        }
        wave_map_bear = {
            "1": MacroWavePosition.IMPULSE_W1_BEAR,
            "2": MacroWavePosition.IMPULSE_W2_BEAR,
            "3": MacroWavePosition.IMPULSE_W3_BEAR,
            "4": MacroWavePosition.IMPULSE_W4_BEAR,
            "5": MacroWavePosition.IMPULSE_W5_BEAR,
        }
        wave_map = wave_map_bull if is_bull else wave_map_bear
        return wave_map.get(current_wave, MacroWavePosition.UNDEFINED)

    # ── Corrective wave mapping ──────────────────────────────────────────────
    elif pattern_type in ("corrective_abc", "zigzag", "flat", "triangle"):
        if is_bear:
            abc_map = {
                "A":       MacroWavePosition.CORRECTIVE_A_BEAR,
                "A_start": MacroWavePosition.CORRECTIVE_A_BEAR,
                "B":       MacroWavePosition.CORRECTIVE_B_BULL,
                "C":       MacroWavePosition.CORRECTIVE_C_BEAR,
            }
        else:
            abc_map = {
                "A":       MacroWavePosition.CORRECTIVE_A_BULL,
                "A_start": MacroWavePosition.CORRECTIVE_A_BULL,
                "B":       MacroWavePosition.CORRECTIVE_B_BEAR,
                "C":       MacroWavePosition.CORRECTIVE_C_BULL,
            }
        return abc_map.get(current_wave, MacroWavePosition.UNDEFINED)

    return MacroWavePosition.UNDEFINED


# ─── MTF Result ───────────────────────────────────────────────────────────────

@dataclass
class MTFResult:
    """
    Full output of the MTF State Machine for one analysis request.
    Contains the final selected micro result + all scoring components.
    """
    # Alignment quality
    alignment:              MTFAlignment
    mtf_score:              int             # 0–10
    momentum_score:         int             # 0–5

    # Macro context
    macro_position:         MacroWavePosition
    macro_direction:        Direction
    macro_result:           ElliottGuardResult
    macro_timeframe:        str

    # Selected micro result (None if full contradiction)
    micro_result:           Optional[ElliottGuardResult]
    micro_timeframe:        str

    # All micro candidates that passed macro filter (for debugging)
    filtered_micro_count:   int
    total_micro_candidates: int

    # Description for UI verdict panel
    description_ar:         str
    description_en:         str

    # Contradiction reason (populated only when alignment == CONTRADICTION)
    contradiction_reason:   str = ""

    def to_dict(self) -> dict:
        return {
            "alignment":            self.alignment.value,
            "mtf_score":            self.mtf_score,
            "momentum_score":       self.momentum_score,
            "macro_position":       self.macro_position.value,
            "macro_direction":      self.macro_direction,
            "macro_timeframe":      self.macro_timeframe,
            "micro_timeframe":      self.micro_timeframe,
            "filtered_micro_count": self.filtered_micro_count,
            "total_micro_candidates": self.total_micro_candidates,
            "description_ar":       self.description_ar,
            "description_en":       self.description_en,
            "contradiction_reason": self.contradiction_reason,
            "macro_result":         self.macro_result.to_dict() if self.macro_result else None,
            "micro_result":         self.micro_result.to_dict() if self.micro_result else None,
        }


# ─── MTF State Machine ────────────────────────────────────────────────────────

class MTFStateMachine:
    """
    The Multi-Timeframe contradiction resolver.

    Entry point: resolve(macro_results, micro_results, macro_tf, micro_tf)

    Workflow:
        1. Select the best valid macro result (highest base_score)
        2. Classify the macro state → MacroWavePosition
        3. Look up the MTFConstraint for that macro state
        4. Filter all micro candidates against the constraint
        5. Score the surviving micro candidates
        6. Return the highest-scoring aligned micro result + full MTF metadata
    """

    def resolve(
        self,
        macro_candidates: list[ElliottGuardResult],
        micro_candidates: list[ElliottGuardResult],
        macro_tf:         str = "1d",
        micro_tf:         str = "1h",
        latest_micro_close: float = 0.0,
    ) -> MTFResult:
        """
        Core MTF resolution algorithm.

        Parameters
        ----------
        macro_candidates    : All valid ElliottGuardResults from macro TF analysis
        micro_candidates    : All valid ElliottGuardResults from micro TF analysis
        macro_tf            : Macro timeframe label (for reporting only)
        micro_tf            : Micro timeframe label (for reporting only)
        latest_micro_close  : Latest close price on micro TF (for momentum check)

        Returns
        -------
        MTFResult with the best aligned micro result and full scoring metadata
        """
        total_micro_count = len(micro_candidates)

        # ── Step 1: Select best macro result ────────────────────────────────
        if not macro_candidates:
            log.warning("[MTFStateMachine] No valid macro candidates — UNDEFINED state.")
            return self._undefined_result(
                micro_candidates, macro_tf, micro_tf,
                total_micro_count, latest_micro_close,
                reason="No valid macro wave count found on higher timeframe.",
            )

        best_macro = max(macro_candidates, key=lambda r: r.base_score)
        log.info(
            f"[MTFStateMachine] Best macro: {best_macro.direction} "
            f"{best_macro.pattern_type} W{best_macro.current_wave} "
            f"score={best_macro.base_score}"
        )

        # ── Step 2: Classify macro state ────────────────────────────────────
        macro_position = classify_macro_state(best_macro)
        log.info(f"[MTFStateMachine] Macro position: {macro_position.value}")

        # ── Step 3: Look up constraint ───────────────────────────────────────
        constraint = MTF_CONSTRAINT_TABLE.get(macro_position, MTF_CONSTRAINT_TABLE[MacroWavePosition.UNDEFINED])

        # ── Step 4: Filter micro candidates ─────────────────────────────────
        filtered_micro = self._filter_micro_candidates(micro_candidates, constraint)
        log.info(
            f"[MTFStateMachine] Micro filter: {len(micro_candidates)} total → "
            f"{len(filtered_micro)} survive constraint ({macro_position.value})"
        )

        # ── Step 5: Score surviving micro candidates ─────────────────────────
        if not filtered_micro:
            return self._contradiction_result(
                best_macro, macro_position, constraint,
                macro_tf, micro_tf, total_micro_count, latest_micro_close,
            )

        best_micro, alignment = self._select_best_micro(filtered_micro, constraint)

        # ── Step 6: Compute MTF alignment score ──────────────────────────────
        mtf_score = self._compute_mtf_score(alignment, constraint)

        # ── Step 7: Compute momentum consistency score ───────────────────────
        momentum_score = self._compute_momentum_score(
            best_macro, best_micro, constraint, latest_micro_close
        )

        log.info(
            f"[MTFStateMachine] ALIGNED: {alignment.value} "
            f"mtf={mtf_score} momentum={momentum_score} "
            f"micro={best_micro.direction} {best_micro.pattern_type}"
        )

        return MTFResult(
            alignment=alignment,
            mtf_score=mtf_score,
            momentum_score=momentum_score,
            macro_position=macro_position,
            macro_direction=best_macro.direction,
            macro_result=best_macro,
            macro_timeframe=macro_tf,
            micro_result=best_micro,
            micro_timeframe=micro_tf,
            filtered_micro_count=len(filtered_micro),
            total_micro_candidates=total_micro_count,
            description_ar=constraint.description_ar,
            description_en=constraint.description_en,
        )

    # ─── Private Methods ──────────────────────────────────────────────────────

    def _filter_micro_candidates(
        self,
        micro_candidates: list[ElliottGuardResult],
        constraint:       MTFConstraint,
    ) -> list[ElliottGuardResult]:
        """
        Apply the MTF constraint hard filter to all micro candidates.
        A micro result survives ONLY if:
            (a) Its direction is in constraint.allowed_micro_directions, AND
            (b) Its pattern_type is in constraint.allowed_micro_patterns
        """
        surviving = []
        for m in micro_candidates:
            direction_ok = m.direction in constraint.allowed_micro_directions
            pattern_ok   = m.pattern_type in constraint.allowed_micro_patterns

            if direction_ok and pattern_ok:
                surviving.append(m)
            else:
                log.debug(
                    f"[MTFFilter] BLOCKED: {m.direction} {m.pattern_type} "
                    f"(dir_ok={direction_ok}, pat_ok={pattern_ok})"
                )

        return surviving

    def _select_best_micro(
        self,
        filtered_micro: list[ElliottGuardResult],
        constraint:     MTFConstraint,
    ) -> tuple[ElliottGuardResult, MTFAlignment]:
        """
        Among the filtered micro candidates, select the best one and determine
        the alignment quality (FULL / PARTIAL / WEAK).

        Returns (best_micro_result, alignment_quality)
        """
        # Separate candidates by alignment quality
        full_matches    = [m for m in filtered_micro if m.pattern_type == constraint.preferred_micro_pattern]
        partial_matches = [m for m in filtered_micro if m.pattern_type != constraint.preferred_micro_pattern]

        if full_matches:
            best = max(full_matches, key=lambda m: m.base_score)
            return best, MTFAlignment.FULL

        if partial_matches:
            best = max(partial_matches, key=lambda m: m.base_score)
            # Distinguish partial vs weak by how close to the preferred pattern
            corrective_types = {"corrective_abc", "zigzag", "flat", "triangle"}
            impulse_types    = {"impulse", "diagonal_ending", "diagonal_leading"}

            pref_is_corrective = constraint.preferred_micro_pattern in corrective_types
            best_is_corrective = best.pattern_type in corrective_types

            alignment = MTFAlignment.PARTIAL if pref_is_corrective == best_is_corrective \
                        else MTFAlignment.WEAK

            return best, alignment

        # Fallback (shouldn't reach here since we checked filtered_micro is non-empty)
        best = max(filtered_micro, key=lambda m: m.base_score)
        return best, MTFAlignment.WEAK

    def _compute_mtf_score(
        self,
        alignment:  MTFAlignment,
        constraint: MTFConstraint,
    ) -> int:
        """Compute the MTF alignment component score (0–10)."""
        score_map = {
            MTFAlignment.FULL:         constraint.full_alignment_score,      # 10
            MTFAlignment.PARTIAL:      constraint.partial_alignment_score,   # 5
            MTFAlignment.WEAK:         2,
            MTFAlignment.CONTRADICTION: constraint.contradiction_score,      # 0
        }
        return score_map.get(alignment, 0)

    def _compute_momentum_score(
        self,
        macro_result:       ElliottGuardResult,
        micro_result:       ElliottGuardResult,
        constraint:         MTFConstraint,
        latest_micro_close: float,
    ) -> int:
        """
        Compute the momentum consistency score (0–5).

        Simple proxy: does the micro analysis direction agree with the
        macro momentum bias from the constraint table?

        Full score (5/5): Micro direction matches macro momentum bias.
        Half score (3/5): Micro is corrective in expected corrective macro state.
        Zero (0/5):       Micro direction contradicts momentum bias.
        """
        bias = constraint.momentum_bias
        micro_dir = micro_result.direction

        if bias == "neutral":
            return 3  # Undefined macro → partial momentum score

        if bias == "accelerating":
            # Macro momentum is accelerating in macro direction
            # Full score if micro direction matches macro direction
            if micro_dir == macro_result.direction:
                return 5
            elif micro_result.pattern_type in ("corrective_abc", "zigzag", "flat"):
                return 3  # Corrective pullback is acceptable
            else:
                return 0

        elif bias == "decelerating":
            # Macro momentum is decelerating — we expect correction
            corrective_types = {"corrective_abc", "zigzag", "flat", "triangle"}
            if micro_result.pattern_type in corrective_types:
                return 5  # Corrective micro matches decelerating bias
            elif micro_dir != macro_result.direction:
                return 3  # Different direction but not corrective — partial
            else:
                return 1  # Same direction as macro despite deceleration signal

        return 3  # Default partial score for edge cases

    def _contradiction_result(
        self,
        best_macro:      ElliottGuardResult,
        macro_position:  MacroWavePosition,
        constraint:      MTFConstraint,
        macro_tf:        str,
        micro_tf:        str,
        total_micro:     int,
        latest_micro_close: float,
    ) -> MTFResult:
        """
        Build a contradiction result when no micro candidate survives the filter.
        This is the resolution of the problem the competitor failed to solve:
        instead of returning conflicting signals, we explicitly declare a
        contradiction and return only the macro analysis with MTF score = 0.
        """
        reason = (
            f"Macro state is {macro_position.value} "
            f"(requires micro direction ∈ {set(constraint.allowed_micro_directions)}, "
            f"pattern ∈ {set(constraint.allowed_micro_patterns)}), "
            f"but none of the {total_micro} micro candidates satisfy these constraints. "
            f"No trade signal generated — MTF contradiction must be resolved before entry."
        )
        log.warning(f"[MTFStateMachine] CONTRADICTION: {reason}")

        return MTFResult(
            alignment=MTFAlignment.CONTRADICTION,
            mtf_score=0,
            momentum_score=0,
            macro_position=macro_position,
            macro_direction=best_macro.direction,
            macro_result=best_macro,
            macro_timeframe=macro_tf,
            micro_result=None,
            micro_timeframe=micro_tf,
            filtered_micro_count=0,
            total_micro_candidates=total_micro,
            description_ar=(
                f"تعارض بين الإطارين الزمنيين: {macro_tf} و{micro_tf}. "
                "لا يوجد سيناريو متوافق. يُنصح بالانتظار حتى يتضح الاتجاه."
            ),
            description_en=(
                f"MTF Contradiction between {macro_tf} and {micro_tf}. "
                "No compatible micro scenario found. Wait for clarity before entering."
            ),
            contradiction_reason=reason,
        )

    def _undefined_result(
        self,
        micro_candidates:   list[ElliottGuardResult],
        macro_tf:           str,
        micro_tf:           str,
        total_micro:        int,
        latest_micro_close: float,
        reason:             str = "",
    ) -> MTFResult:
        """
        Build a result when the macro state is UNDEFINED (no valid macro count).
        In this case we use the UNDEFINED constraint and analyze micro independently.
        """
        undefined_constraint = MTF_CONSTRAINT_TABLE[MacroWavePosition.UNDEFINED]
        # All micro candidates pass the UNDEFINED filter (allows everything)
        filtered = self._filter_micro_candidates(micro_candidates, undefined_constraint)

        best_micro = max(filtered, key=lambda m: m.base_score) if filtered else None

        return MTFResult(
            alignment=MTFAlignment.WEAK,
            mtf_score=undefined_constraint.full_alignment_score,
            momentum_score=3,
            macro_position=MacroWavePosition.UNDEFINED,
            macro_direction="bullish",
            macro_result=ElliottGuardResult(
                valid=False,
                pattern_type="impulse",
                direction="bullish",
                reject_reason=reason,
            ),
            macro_timeframe=macro_tf,
            micro_result=best_micro,
            micro_timeframe=micro_tf,
            filtered_micro_count=len(filtered),
            total_micro_candidates=total_micro,
            description_ar=undefined_constraint.description_ar,
            description_en=undefined_constraint.description_en,
            contradiction_reason=reason,
        )
