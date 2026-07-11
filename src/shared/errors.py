"""Domain error types surfaced to the user by the CLI."""
from __future__ import annotations


class BaldrickError(Exception):
    """Base class for expected, user-facing errors."""


class MapError(BaldrickError):
    """Raised when a route cannot be placed on any supported map."""


class ToTError(BaldrickError):
    """Raised when time-on-target constraints are inconsistent or impossible."""


class FuelError(BaldrickError):
    """Raised when a route cannot be flown within fuel/reserve limits."""
