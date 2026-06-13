"""Deprecated shim — use sedar.legacy.breaker instead."""

import warnings

warnings.warn(
    "Import sedar.legacy.breaker instead of root breaker.py",
    DeprecationWarning,
    stacklevel=2,
)

from sedar.legacy.breaker import *  # noqa: F403
