"""
Slot allocation engine — pure business logic with no Flask dependencies.

Rules derived from the VBA macro ``AllocateStudentsWithLimitCarryForward``.
A row is considered "free" when its Period column contains "-".

The public API is a single ``allocate`` function that accepts a DataFrame
and a list of roll numbers and returns a dictionary describing the
allocation, not-available students, overflow, and a summary.
"""
from __future__ import annotations

import re
import pandas as pd


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def allocate(
    df_master: pd.DataFrame,
    roll_numbers: list[str],
    day_filter: str = "",
    panel_count: int = 1,
    slot_limit: int = 10,
    selected_slots: list[str] | None = None,
) -> dict:
    """Perform slot allocation.

    Parameters
    ----------
    df_master : pd.DataFrame
        Master timetable loaded from Google Sheets (normalized column names).
    roll_numbers : list[str]
        Roll numbers entered by the user.
    day_filter : str
        Optional day filter; empty string means all days.
    panel_count : int
        Number of panels (>=1).
    slot_limit : int
        Max students per panel per slot.
    selected_slots : list[str] | None
        Specific slots chosen by the user; if None all free slots are used.

    Returns
    -------
    dict
        Dictionary containing keys `allocated`, `not_available`,
        `overflow`, `summary`, and `slot_totals`.
    """
    eligible = _deduplicate_rolls(roll_numbers)
    if not eligible:
        return _empty_result("No valid roll numbers provided.")

    cols = _resolve_columns(df_master)

    free_df = _filter_free_rows(df_master, cols, day_filter)
    if free_df.empty:
        return _empty_result("No free slots found in the master table.")

    if selected_slots:
        slot_set = {s.strip() for s in selected_slots if s.strip()}
    else:
        slot_set = set(free_df[cols["slot"]].astype(str).str.strip().unique())

    if not slot_set:
        return _empty_result("No slots selected.")

    # ── Split into predefined vs custom slots ──
    sheet_slots = set(free_df[cols["slot"]].astype(str).str.strip().unique())
    predefined_slots = slot_set & sheet_slots
    custom_slots = slot_set - sheet_slots

    sorted_slots = sorted(slot_set, key=_parse_slot_time)

    student_info: dict[str, dict] = {}
    student_free_count: dict[str, int] = {}
    slot_students: dict[str, list[dict]] = {s: [] for s in sorted_slots}

    # ── Existing exact-match logic for predefined slots ──
    for _, row in free_df.iterrows():
        roll = str(row[cols["roll"]]).strip()
        slot_key = str(row[cols["slot"]]).strip()

        if roll not in eligible:
            continue
        if slot_key not in predefined_slots:
            continue

        name = str(row[cols["name"]]).strip()
        batch = str(row[cols["batch"]]).strip()

        student_info.setdefault(roll, {"name": name, "batch": batch})
        student_free_count[roll] = student_free_count.get(roll, 0) + 1

        slot_students[slot_key].append(
            {"roll_no": roll, "name": name, "batch": batch, "slot": slot_key}
        )

    # ── Time-range matching for custom slots ──
    if custom_slots:
        _find_custom_slot_candidates(
            free_df, cols, eligible, custom_slots,
            student_info, student_free_count, slot_students,
        )

    if not student_info:
        return _empty_result(
            "No eligible students have free slots in the selected time range."
        )

    used: set[str] = set()
    allocated: list[dict] = []
    slot_totals: dict[str, int] = {}

    for slot in sorted_slots:
        candidates = slot_students.get(slot, [])
        if not candidates:
            slot_totals[slot] = 0
            continue

        candidates.sort(key=lambda c: student_free_count.get(c["roll_no"], 0))

        count_allocated = 0
        current_panel = 1
        panel_allocation_count = 0

        for cand in candidates:
            roll = cand["roll_no"]
            if roll in used:
                continue

            allocated.append({
                "slot": slot,
                "roll_no": roll,
                "name": cand["name"],
                "batch": cand["batch"],
                "panel": current_panel,
            })
            used.add(roll)
            count_allocated += 1

            if panel_count > 1:
                panel_allocation_count += 1
                if panel_allocation_count >= slot_limit:
                    panel_allocation_count = 0
                    current_panel += 1
                    if current_panel > panel_count:
                        break
            else:
                if count_allocated >= slot_limit:
                    break

        slot_totals[slot] = count_allocated

    not_available: list[dict] = []
    reason = (
        f"No free slots in selected time ({day_filter})"
        if day_filter
        else "No free slots in selected time"
    )

    for roll in eligible:
        if roll not in student_info:
            name, batch = _lookup_student(df_master, cols, roll)
            not_available.append({
                "roll_no": roll,
                "name": name,
                "batch": batch,
                "reason": reason,
            })

    overflow: list[dict] = []
    for roll, info in student_info.items():
        if roll not in used:
            eligible_free = []
            for slot in sorted_slots:
                for cand in slot_students.get(slot, []):
                    if cand["roll_no"] == roll:
                        eligible_free.append(slot)
                        break
            overflow.append({
                "roll_no": roll,
                "name": info["name"],
                "batch": info["batch"],
                "eligible_slots": ", ".join(eligible_free),
            })

    summary = {
        "total_roll": len(eligible),
        "allocated_count": len(used),
        "not_available_count": len(not_available),
        "overflow_count": len(overflow),
    }

    return {
        "allocated": allocated,
        "not_available": not_available,
        "overflow": overflow,
        "summary": summary,
        "slot_totals": slot_totals,
    }


# ---------------------------------------------------------------------------
# private helpers
# ---------------------------------------------------------------------------


def _deduplicate_rolls(roll_numbers: list[str]) -> set[str]:
    result = set()
    for r in roll_numbers:
        r = str(r).strip()
        if r:
            result.add(r)
    return result


def _resolve_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map logical names to actual DataFrame columns.

    The only *required* keys are `roll`, `name`, `batch`, `day`, and `slot`.
    Existing code sometimes had a `status` column; it is ignored.
    """
    mapping = {
        "roll": ["roll_no", "rollno", "roll", "roll_number", "enrollment"],
        "name": ["name", "student_name", "studentname"],
        "batch": ["batch", "section", "class"],
        "day": ["day", "weekday"],
        "slot": ["slot", "time_slot", "timeslot", "time"],
        "period": ["period", "status", "availability", "free/class"],
    }
    resolved: dict[str, str] = {}
    for key, candidates in mapping.items():
        for cand in candidates:
            if cand in df.columns:
                resolved[key] = cand
                break
        if key not in resolved:
            for cand in candidates:
                for col in df.columns:
                    if cand in col:
                        resolved[key] = col
                        break
                if key in resolved:
                    break
        if key not in resolved:
            raise KeyError(
                f"Cannot find column for '{key}'. Tried: {candidates}. "
                f"Available: {list(df.columns)}"
            )
    # status is optional; we don't even return it
    return resolved


def _filter_free_rows(
    df: pd.DataFrame, cols: dict[str, str], day_filter: str
) -> pd.DataFrame:
    """Return rows where period == "-" (free period).

    This mirrors VBA: Trim(CStr(wsMaster.Cells(i, 7).Value)) = "-"
    Column 7 in the sheet is the Period column.
    """
    mask = df[cols["period"]].astype(str).str.strip() == "-"
    if day_filter:
        mask &= (
            df[cols["day"]].astype(str).str.strip().str.lower() == day_filter.lower()
        )
    return df.loc[mask].copy()


def _parse_slot_time(slot: str) -> float:
    """Convert a slot string into a sortable float (minutes since midnight).

    Handles AM/PM format (e.g. '10:35 AM - 11:25 AM') via _parse_time_ampm,
    and falls back to raw numeric parsing for legacy formats.
    """
    try:
        start_str = slot.split("-")[0].strip()
        # Try AM/PM-aware parsing first
        result = _parse_time_ampm(start_str)
        if result is not None:
            return float(result)
        # Fallback: raw numeric (e.g. "10:30" without AM/PM)
        parts = start_str.replace(".", ":").split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        return hours * 60.0 + minutes
    except (ValueError, IndexError):
        return 9999.0


def _lookup_student(
    df: pd.DataFrame, cols: dict[str, str], roll: str
) -> tuple[str, str]:
    match = df.loc[df[cols["roll"]].astype(str).str.strip() == roll]
    if not match.empty:
        first = match.iloc[0]
        return str(first[cols["name"]]).strip(), str(first[cols["batch"]]).strip()
    return "N/A", "N/A"


def _empty_result(message: str) -> dict:
    return {
        "allocated": [],
        "not_available": [],
        "overflow": [],
        "summary": {
            "total_roll": 0,
            "allocated_count": 0,
            "not_available_count": 0,
            "overflow_count": 0,
            "error": message,
        },
        "slot_totals": {},
    }


# ---------------------------------------------------------------------------
# custom slot helpers — time-range merging
# ---------------------------------------------------------------------------

def _parse_time_ampm(s: str) -> int | None:
    """Parse a time string like '10:35 AM' into minutes since midnight.

    Returns None if parsing fails.
    """
    s = s.strip().upper()
    m = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", s)
    if not m:
        return None
    hours, minutes, period = int(m.group(1)), int(m.group(2)), m.group(3)
    if period == "AM" and hours == 12:
        hours = 0
    elif period == "PM" and hours != 12:
        hours += 12
    return hours * 60 + minutes


def _parse_slot_range(slot: str) -> tuple[int, int] | None:
    """Parse a slot string like '10:35 AM - 11:25 AM' into (start_min, end_min).

    Returns None if parsing fails.
    """
    parts = slot.split("-")
    if len(parts) < 2:
        return None
    start = _parse_time_ampm(parts[0])
    end = _parse_time_ampm(parts[-1])
    if start is None or end is None:
        return None
    return (start, end)


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge sorted, potentially consecutive/overlapping intervals.

    E.g. [(630,680),(680,730)] → [(630,730)]
    """
    if not intervals:
        return []
    intervals.sort()
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:  # consecutive or overlapping
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _find_custom_slot_candidates(
    free_df: pd.DataFrame,
    cols: dict[str, str],
    eligible: set[str],
    custom_slots: set[str],
    student_info: dict[str, dict],
    student_free_count: dict[str, int],
    slot_students: dict[str, list[dict]],
) -> None:
    """Populate slot_students for custom slots using time-range merging.

    For each eligible student, collects all their free slot intervals,
    merges consecutive ones, then checks if each custom slot's time range
    falls completely within any merged block.
    """
    # Parse custom slots into (start_min, end_min)
    parsed_custom: list[tuple[str, int, int]] = []
    for cs in custom_slots:
        rng = _parse_slot_range(cs)
        if rng:
            parsed_custom.append((cs, rng[0], rng[1]))

    if not parsed_custom:
        return

    # Build per-student free intervals from ALL free rows (not just selected slots)
    student_intervals: dict[str, list[tuple[int, int]]] = {}
    student_lookup: dict[str, tuple[str, str]] = {}  # roll -> (name, batch)

    for _, row in free_df.iterrows():
        roll = str(row[cols["roll"]]).strip()
        if roll not in eligible:
            continue

        slot_str = str(row[cols["slot"]]).strip()
        rng = _parse_slot_range(slot_str)
        if rng is None:
            continue

        student_intervals.setdefault(roll, []).append(rng)
        if roll not in student_lookup:
            student_lookup[roll] = (
                str(row[cols["name"]]).strip(),
                str(row[cols["batch"]]).strip(),
            )

    # For each student, merge their intervals and check each custom slot
    for roll, intervals in student_intervals.items():
        merged = _merge_intervals(intervals)
        name, batch = student_lookup[roll]

        for cs_name, cs_start, cs_end in parsed_custom:
            for block_start, block_end in merged:
                if cs_start >= block_start and cs_end <= block_end:
                    # Student is available for this custom slot
                    student_info.setdefault(roll, {"name": name, "batch": batch})
                    student_free_count[roll] = student_free_count.get(roll, 0) + 1
                    slot_students[cs_name].append(
                        {"roll_no": roll, "name": name, "batch": batch, "slot": cs_name}
                    )
                    break  # found a covering block, no need to check others
