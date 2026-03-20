"""
Time slot validation — strict format and logic checks.

Validates custom time slots in the format "HH:MM AM/PM - HH:MM AM/PM".
Used by both the route handler (server-side) and can be referenced
for consistency with the frontend validation in app.js.
"""
from __future__ import annotations

import re

# Maximum allowed slot duration in minutes (2 hours)
MAX_DURATION_MINUTES = 120


def validate_time_slot(slot_str: str) -> tuple[bool, str, str]:
    """Validate and normalize a time slot string.

    Parameters
    ----------
    slot_str : str
        Raw user input, e.g. "9:45 AM - 10:15 AM".

    Returns
    -------
    tuple[bool, str, str]
        (is_valid, error_message, normalized_slot)
        On success: (True, "", "9:45 AM - 10:15 AM")
        On failure: (False, "descriptive error", "")
    """
    if not slot_str or not slot_str.strip():
        return False, "Please enter a time slot.", ""

    raw = slot_str.strip()

    # ── Step 1: Overall format check ──
    # Accept "HH:MM AM/PM - HH:MM AM/PM" with flexible spacing/case
    pattern = re.compile(
        r"^(\d{1,2}):(\d{2})\s*(AM|PM)\s*-\s*(\d{1,2}):(\d{2})\s*(AM|PM)$",
        re.IGNORECASE,
    )
    m = pattern.match(raw)
    if not m:
        return (
            False,
            "Invalid time format. Please use 'HH:MM AM/PM - HH:MM AM/PM'",
            "",
        )

    start_h, start_m_str, start_period = int(m.group(1)), m.group(2), m.group(3).upper()
    end_h, end_m_str, end_period = int(m.group(4)), m.group(5), m.group(6).upper()
    start_m = int(start_m_str)
    end_m = int(end_m_str)

    # ── Step 2: Hour validation ──
    if start_h < 1 or start_h > 12:
        return False, "Invalid hour. Use values between 1 and 12", ""
    if end_h < 1 or end_h > 12:
        return False, "Invalid hour. Use values between 1 and 12", ""

    # ── Step 3: Minute validation ──
    if start_m < 0 or start_m > 59:
        return False, "Minutes must be between 00 and 59", ""
    if end_m < 0 or end_m > 59:
        return False, "Minutes must be between 00 and 59", ""

    # ── Convert to minutes since midnight ──
    start_total = _to_minutes(start_h, start_m, start_period)
    end_total = _to_minutes(end_h, end_m, end_period)

    # ── Step 4: Same start and end ──
    if start_total == end_total:
        return False, "Start and end time cannot be the same", ""

    # ── Step 5: End must be after start ──
    if end_total <= start_total:
        return False, "End time must be later than start time", ""

    # ── Step 6: Duration cap ──
    duration = end_total - start_total
    if duration > MAX_DURATION_MINUTES:
        return (
            False,
            f"Slot duration must not exceed {MAX_DURATION_MINUTES // 60} hours",
            "",
        )

    # ── Normalize the slot string ──
    normalized = (
        f"{start_h}:{start_m_str} {start_period} - {end_h}:{end_m_str} {end_period}"
    )

    return True, "", normalized


def _to_minutes(hours: int, minutes: int, period: str) -> int:
    """Convert 12-hour time to minutes since midnight."""
    if period == "AM" and hours == 12:
        hours = 0
    elif period == "PM" and hours != 12:
        hours += 12
    return hours * 60 + minutes
