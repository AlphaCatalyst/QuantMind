"""Canonical factor-to-signal contracts for QuantMind 2.0."""

from .models import FactorSignalInput, UnifiedSignalSpec
from .service import build_unified_signal, parse_spec, validate_signal_artifact

__all__ = [
    "FactorSignalInput", "UnifiedSignalSpec", "build_unified_signal",
    "parse_spec", "validate_signal_artifact",
]
