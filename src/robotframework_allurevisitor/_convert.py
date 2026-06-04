"""Timing, status, and identity conversion helpers.

These translate Robot Framework result-model values into the units and
conventions the Allure model expects, independent of the visitor traversal.
"""

from __future__ import annotations

from datetime import datetime

from allure_commons.model2 import Status, StatusDetails
from allure_commons.utils import md5

# Substrings that suggest a Robot failure is an environment/library error
# (Allure "broken") rather than a plain assertion failure (Allure "failed").
_ERROR_HINTS = (
    "no keyword with name",
    "importing",
    "syntax",
    "resolving variable",
    "evaluating",
    "timeout",
    "no library",
    "module",
)


def to_ms(value: datetime | str | None) -> int | None:
    """Convert a Robot Framework timestamp to epoch milliseconds.

    Handles RF 7+ ``datetime`` values, legacy RF 4-6 strings
    (``YYYYMMDD HH:MM:SS.fff``), and ``None``.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return int(round(value.timestamp() * 1000))
    if isinstance(value, str):
        if not value or value == "N/A":
            return None
        parsed = datetime.strptime(value, "%Y%m%d %H:%M:%S.%f")
        return int(round(parsed.timestamp() * 1000))
    return None


def status_details(item) -> StatusDetails | None:  # noqa: ANN001 - RF model object
    """Build ``StatusDetails`` from an item's message, or ``None`` if empty."""
    message = getattr(item, "message", None)
    if not message:
        return None
    return StatusDetails(message=message)


def _looks_like_error(item) -> bool:  # noqa: ANN001
    message = (getattr(item, "message", "") or "").lower()
    if not message:
        return False
    if "!=" in message or "==" in message:
        # Assertion comparison output -> a normal failure, not an error.
        return False
    return any(hint in message for hint in _ERROR_HINTS)


def status_of(item) -> tuple[str, StatusDetails | None]:  # noqa: ANN001
    """Map a Robot status to an Allure ``(status, statusDetails)`` pair."""
    status = getattr(item, "status", None)
    if status == "PASS":
        return Status.PASSED, None
    if status in ("SKIP", "NOT RUN", "NOT_RUN"):
        return Status.SKIPPED, status_details(item)
    if status == "FAIL":
        details = status_details(item)
        if _looks_like_error(item):
            return Status.BROKEN, details
        return Status.FAILED, details
    return Status.UNKNOWN, status_details(item)


def history_id(full_name: str, parameters=None) -> str:  # noqa: ANN001
    """Stable identity across reruns: ``md5(full_name [+ sorted params])``."""
    parts = [full_name]
    if parameters:
        ordered = sorted(parameters, key=lambda p: (p.name or "", str(p.value)))
        parts += [f"{p.name}={p.value}" for p in ordered]
    return md5(*parts)
