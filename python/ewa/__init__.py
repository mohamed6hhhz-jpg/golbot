"""
ewa/__init__.py

EWA (Elliott Wave Analysis) Python Package
==========================================
Exports the public API surface for all EWA engine modules.
Import order matters: pivot_engine has no internal deps, elliott_guard
imports from pivot_engine, mtf_state_machine imports from elliott_guard.
"""

from .pivot_engine import (
    OHLCVBar,
    Pivot,
    PivotEngineResult,
    detect_pivots,
    extract_wave_candidates,
    compute_atr,
    compute_prominence_threshold,
    compute_leg_lengths,
    compute_pivot_slopes,
    nearest_fibonacci,
    is_fibonacci_confluence,
)

from .elliott_guard import (
    ElliottGuard,
    ElliottGuardResult,
    RuleResult,
    GuidelineResult,
    Direction,
    PatternType,
)

from .mtf_state_machine import (
    MTFStateMachine,
    MTFResult,
    MTFAlignment,
    MacroWavePosition,
    MTFConstraint,
    classify_macro_state,
    MTF_CONSTRAINT_TABLE,
)

__all__ = [
    # pivot_engine
    "OHLCVBar", "Pivot", "PivotEngineResult",
    "detect_pivots", "extract_wave_candidates",
    "compute_atr", "compute_prominence_threshold",
    "compute_leg_lengths", "compute_pivot_slopes",
    "nearest_fibonacci", "is_fibonacci_confluence",

    # elliott_guard
    "ElliottGuard", "ElliottGuardResult",
    "RuleResult", "GuidelineResult",
    "Direction", "PatternType",

    # mtf_state_machine
    "MTFStateMachine", "MTFResult", "MTFAlignment",
    "MacroWavePosition", "MTFConstraint",
    "classify_macro_state", "MTF_CONSTRAINT_TABLE",
]

__version__ = "1.0.0"
