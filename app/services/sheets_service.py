"""
Google Sheets service layer — hides all interactions with the
Google Sheets API and returns "clean" pandas DataFrames to the
rest of the application.

Responsibilities:
- load service account credentials from app config
- open a spreadsheet by URL
- normalise column names (strip/lower/underscore)
- perform simple queries such as available slots
- translate common API errors into Python exceptions with useful
  messages for the caller

This module has no Flask-specific dependencies except for accessing
`current_app.config` when a client is created.
"""
from __future__ import annotations

import re
import pandas as pd
import gspread
from gspread.exceptions import APIError, SpreadsheetNotFound
from google.oauth2.service_account import Credentials
from flask import current_app


# read-only scopes are sufficient for our use case
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


# ---- internal helpers ----------------------------------------------------

def _get_client() -> gspread.Client:
    """Return an authorised gspread client using the service account file."""
    creds_path = current_app.config.get("GOOGLE_CREDS_FILE")
    if not creds_path:
        raise RuntimeError("GOOGLE_CREDS_FILE not set in configuration")

    credentials = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return gspread.authorize(credentials)


def extract_sheet_id(url: str) -> str:
    """Extract the spreadsheet ID from a full Google Sheets URL.

    Raises
    ------
    ValueError
        If the URL does not match the expected pattern.
    """
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError(
            "Invalid Google Sheets URL. "
            "Expected format: https://docs.google.com/spreadsheets/d/{sheet_id}/..."
        )
    return match.group(1)


# ---- public API ----------------------------------------------------------

def load_master_timetable(sheet_url: str, worksheet_name: str | None = None) -> pd.DataFrame:
    """Load the master timetable into a pandas DataFrame.

    The returned frame has column names normalised to lowercase with
    spaces replaced by underscores.  No further validation is performed
    here; callers should inspect the DataFrame for required columns.

    Parameters
    ----------
    sheet_url : str
        Full URL of the Google Sheet.
    worksheet_name : str | None
        Name of the worksheet/tab to open.  Defaults to the first sheet.

    Returns
    -------
    pd.DataFrame
        DataFrame containing the sheet data.

    Raises
    ------
    ValueError
        If the URL is invalid or the sheet contains no data.
    gspread.exceptions.APIError
        For permission/transport errors; bubbled up to caller.
    """
    client = _get_client()

    sheet_id = extract_sheet_id(sheet_url)
    try:
        spreadsheet = client.open_by_key(sheet_id)
    except SpreadsheetNotFound as exc:
        raise ValueError("Spreadsheet not found or access denied") from exc
    except APIError:
        # bubble up; caller can choose to wrap/log
        raise

    worksheet = spreadsheet.worksheet(worksheet_name) if worksheet_name else spreadsheet.sheet1

    records = worksheet.get_all_records()
    if not records:
        raise ValueError("The sheet appears to be empty or has no data rows.")

    df = pd.DataFrame(records)

    # normalise column names
    df.columns = [
        col.strip().lower().replace(" ", "_").replace(".", "")
        for col in df.columns
    ]

    return df


def get_available_slots(
    sheet_url: str,
    day_filter: str = "",
    worksheet_name: str | None = None,
) -> list[str]:
    """Return sorted list of slots where at least one free row exists.

    A "free" row is one whose ``period`` column contains ``"-"``.
    This mirrors the VBA macro which checks column 7 (Period) for ``"-"``.

    Parameters
    ----------
    sheet_url : str
        Google Sheets URL.
    day_filter : str
        Optional day name (case‑insensitive). Empty means all days.
    worksheet_name : str | None
        Specific worksheet/tab name if required.
    """
    df = load_master_timetable(sheet_url, worksheet_name)

    # Locate canonical column names
    period_col = _find_column(df, ["period", "status", "availability"])
    slot_col = _find_column(df, ["slot", "time_slot", "timeslot", "time"])
    day_col = _find_column(df, ["day", "weekday"])

    # Free rows: period == "-" (VBA: Trim(CStr(wsMaster.Cells(i, 7).Value)) = "-")
    mask = df[period_col].astype(str).str.strip() == "-"
    if day_filter:
        mask &= (
            df[day_col].astype(str).str.strip().str.lower() == day_filter.lower()
        )

    free_slots = df.loc[mask, slot_col].astype(str).str.strip().unique().tolist()
    free_slots = [s for s in free_slots if s]

    free_slots.sort(key=_parse_slot_time)
    return free_slots


# ---- utilities ----------------------------------------------------------

def _find_column(df: pd.DataFrame, candidates: list[str]) -> str:
    """Return the first column name matching any of the candidates.

    Raises KeyError if none of the candidates are found.
    """
    for cand in candidates:
        if cand in df.columns:
            return cand
    for cand in candidates:
        for col in df.columns:
            if cand in col:
                return col
    raise KeyError(
        f"Could not find a column matching any of {candidates}. "
        f"Available columns: {list(df.columns)}"
    )


def _parse_slot_time(slot: str) -> float:
    """Convert a slot string into a sortable float (minutes since midnight)."""
    import re
    try:
        start = slot.split("-")[0].strip().upper()
        m = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", start)
        if m:
            hours, minutes, period = int(m.group(1)), int(m.group(2)), m.group(3)
            if period == "AM" and hours == 12:
                hours = 0
            elif period == "PM" and hours != 12:
                hours += 12
            return float(hours * 60 + minutes)
        # Fallback: raw numeric
        parts = start.replace(".", ":").split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        return hours * 60.0 + minutes
    except Exception:
        return 9999.0
