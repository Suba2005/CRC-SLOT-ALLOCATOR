"""
Slot allocation engine — direct port of the VBA macro
``AllocateStudentsWithLimitCarryForward``.

This module contains the pure business logic with NO Flask dependencies,
making it testable and reusable from both Flask routes and MCP tools.

Algorithm Overview (ported from VBA)
-------------------------------------
1. Collect & deduplicate roll numbers from user input.
2. Scan the master table for rows where roll_no is empty (free period).
3. Apply day filter and selected-slot filter.
4. Count how many free slots each eligible student has.
5. For each selected time slot (sorted by start time):
   a. Gather all eligible, not-yet-allocated students available in that slot.
   b. Sort them ASCENDING by their free-slot count (fewest-first priority —
      students with fewer options are allocated first).
   c. Allocate up to (panel_count × slot_limit) students, rotating across
      panels with a per-panel cap of slot_limit.
6. Produce three result sets:
   - allocated: students assigned to a slot+panel
   - not_available: students from the roll list who have NO free slots
     in the selected times
   - overflow: students who had free slots but weren't allocated because
     capacity was reached
7. Return an allocation summary with counts.
"""
from __future__ import annotations
import pandas as pd


# ── Public API ─────────────────────────────────────────────────────────────

def allocate(
    df_master: pd.DataFrame,
    roll_numbers: list[str],
    day_filter: str = "",
    panel_count: int = 1,
    slot_limit: int = 10,
    selected_slots: list[str] | None = None,
) -> dict:
    """
    Run the slot allocation algorithm.

    Parameters
    ----------
    df_master : pd.DataFrame
        Master timetable loaded from Google Sheets.
    roll_numbers : list[str]
        Raw roll numbers provided by the user.
    day_filter : str
        Optional day name filter (e.g. "Monday").  Empty string = all days.
    panel_count : int
        Number of parallel panels (≥ 1).
    slot_limit : int
        Maximum students per panel per slot.
    selected_slots : list[str] | None
        Specific time-slot strings the user selected.  If None, all free
        slots that match the day filter are used.

    Returns
    -------
    dict
        {
            "allocated": [
                {"slot": str, "roll_no": str, "name": str,
                 "batch": str, "panel": int},
                ...
            ],
            "not_available": [
                {"roll_no": str, "name": str, "batch": str, "reason": str},
                ...
            ],
            "overflow": [
                {"roll_no": str, "name": str, "batch": str,
                 "eligible_slots": str},
                ...
            ],
            "summary": {
                "total_roll": int,
                "allocated_count": int,
                "not_available_count": int,
                "overflow_count": int,
            },
            "slot_totals": {
                "<slot_name>": int, ...
            }
        }
    """
    # ── Step 1: Deduplicate roll numbers (mirrors VBA eligibleDict) ──
    eligible = _deduplicate_rolls(roll_numbers)
    if not eligible:
        return _empty_result("No valid roll numbers provided.")

    # ── Identify columns ──
    cols = _resolve_columns(df_master)

    # ── Step 2 & 3: Filter free rows matching day + selected slots ──
    free_df = _filter_free_rows(df_master, cols, day_filter)
    if free_df.empty:
        return _empty_result("No free slots found in the master table.")

    # Build the set of available slot keys
    if selected_slots:
        slot_set = set(s.strip() for s in selected_slots if s.strip())
    else:
        slot_set = set(free_df[cols["slot"]].astype(str).str.strip().unique())

    if not slot_set:
        return _empty_result("No slots selected.")

    # ── Sort selected slots by start time (mirrors VBA SortTimeSlots) ──
    sorted_slots = sorted(slot_set, key=_parse_slot_time)

    # ── Step 4: Build per-student and per-slot maps ──
    # student_info: {roll: {"name": ..., "batch": ...}}
    # student_free_count: {roll: int}
    # slot_students: {slot: [{roll, name, batch, slot}, ...]}
    student_info: dict[str, dict] = {}
    student_free_count: dict[str, int] = {}
    slot_students: dict[str, list[dict]] = {s: [] for s in sorted_slots}

    for _, row in free_df.iterrows():
        roll = str(row[cols["roll"]]).strip()
        slot_key = str(row[cols["slot"]]).strip()

        if roll not in eligible:
            continue
        if slot_key not in slot_set:
            continue

        name = str(row[cols["name"]]).strip()
        batch = str(row[cols["batch"]]).strip()

        if roll not in student_info:
            student_info[roll] = {"name": name, "batch": batch}

        student_free_count[roll] = student_free_count.get(roll, 0) + 1

        slot_students[slot_key].append(
            {"roll_no": roll, "name": name, "batch": batch, "slot": slot_key}
        )

    if not student_info:
        return _empty_result(
            "No eligible students have free slots in the selected time range."
        )

    # ── Step 5 & 6: Allocate slot-by-slot ──
    used: set[str] = set()             # Already-allocated rolls
    allocated: list[dict] = []         # Final allocated rows
    slot_totals: dict[str, int] = {}   # Count per slot

    for slot in sorted_slots:
        candidates = slot_students.get(slot, [])
        if not candidates:
            slot_totals[slot] = 0
            continue

        # Sort candidates by ascending free-slot count (fewest-first priority)
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

    # ── Step 7a: Students NOT available (no free slots at all) ──
    not_available: list[dict] = []
    reason = (
        f"No free slots in selected time ({day_filter})"
        if day_filter
        else "No free slots in selected time"
    )

    # Look up name/batch from master for students not in student_info
    for roll in eligible:
        if roll not in student_info:
            name, batch = _lookup_student(df_master, cols, roll)
            not_available.append({
                "roll_no": roll,
                "name": name,
                "batch": batch,
                "reason": reason,
            })

    # ── Step 7b: Overflow — had free slots but not allocated ──
    overflow: list[dict] = []
    for roll, info in student_info.items():
        if roll not in used:
            # Collect which selected slots this student was free in
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

    # ── Summary ──
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


# ── Private helpers ────────────────────────────────────────────────────────

def _deduplicate_rolls(roll_numbers: list[str]) -> set[str]:
    """Clean and deduplicate roll numbers."""
    result = set()
    for r in roll_numbers:
        r = str(r).strip()
        if r:
            result.add(r)
    return result


def _resolve_columns(df: pd.DataFrame) -> dict[str, str]:
    """
    Map logical column names to actual DataFrame column names.
    The master table may have various header styles.

    Required: roll, name, batch, day, slot, period.
    Optional: sno.
    """
    mapping = {
        "roll": ["roll_no", "rollno", "roll", "roll_number", "enrollment"],
        "name": ["name", "student_name", "studentname"],
        "batch": ["batch", "section", "class"],
        "day": ["day", "weekday"],
        "slot": ["slot", "time_slot", "timeslot", "time"],
        "period": ["period", "status", "availability", "free/class"],
    }
    # Optional columns — resolved if present, silently skipped if not
    optional_mapping = {
        "sno": ["sno", "s_no", "s.no", "serial", "sl_no", "slno"],
    }
    resolved = {}
    for key, candidates in mapping.items():
        for cand in candidates:
            if cand in df.columns:
                resolved[key] = cand
                break
        if key not in resolved:
            # Fuzzy fallback
            for cand in candidates:
                for col in df.columns:
                    if cand in col:
                        resolved[key] = col
                        break
                if key in resolved:
                    break
        if key not in resolved:
            raise KeyError(
                f"Cannot find column for '{key}'. "
                f"Tried: {candidates}. Available: {list(df.columns)}"
            )
    # Resolve optional columns (no error if missing)
    for key, candidates in optional_mapping.items():
        for cand in candidates:
            if cand in df.columns:
                resolved[key] = cand
                break
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
            df[cols["day"]].astype(str).str.strip().str.lower()
            == day_filter.lower()
        )
    return df.loc[mask].copy()


def _parse_slot_time(slot: str) -> float:
    """
    Parse a time-slot string into a sortable float.
    Mirrors VBA ParseTime: takes the start time from "HH:MM - HH:MM".
    """
    try:
        start_str = slot.split("-")[0].strip()
        parts = start_str.replace(".", ":").split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        return hours + minutes / 60.0
    except (ValueError, IndexError):
        return 9999.0


def _lookup_student(
    df: pd.DataFrame, cols: dict[str, str], roll: str
) -> tuple[str, str]:
    """Look up student name and batch from master table by roll number."""
    match = df.loc[df[cols["roll"]].astype(str).str.strip() == roll]
    if not match.empty:
        first = match.iloc[0]
        return str(first[cols["name"]]).strip(), str(first[cols["batch"]]).strip()
    return "N/A", "N/A"


def _empty_result(message: str) -> dict:
    """Return an empty-but-valid result structure with an error message."""
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
