"""Deprecated shim — use sedar.legacy.scrape instead."""

import warnings

warnings.warn(
    "Import sedar.legacy.scrape instead of root scrape.py",
    DeprecationWarning,
    stacklevel=2,
)

from sedar.legacy.scrape import *  # noqa: E402, F403
