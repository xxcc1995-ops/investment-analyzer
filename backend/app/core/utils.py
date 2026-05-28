"""Shared utility functions for backend services."""

import math
from typing import Optional, Any


def safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert a value to float.

    Handles None, empty strings, '-', NaN, Inf, and non-numeric types.
    Returns `default` (None) on failure.
    """
    if val is None or val == '' or val == '-':
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


def safe_float_or_zero(val: Any) -> float:
    """safe_float that returns 0.0 instead of None."""
    return safe_float(val, default=0.0)
