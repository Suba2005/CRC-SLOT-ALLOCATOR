"""
Google Sheets integration — read master timetable via gspread.

Architecture: App / MCP → this module → Google Sheets API
"""
import re
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from flask import current_app


# Google API scopes for Sheets (read-only is sufficient)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_client() -> gspread.Client:
    """Create an authorised gspread client using the service account JSON."""
    creds_path = current_app.config["GOOGLE_CREDS_FILE"]
    credentials = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return gspread.authorize(credentials)


def extract_sheet_id(url: str) -> str:
    """
    Extract the spreadsheet ID from a Google Sheets URL.

    Supports URLs like:
        https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit
        https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=0
    """
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError(
            "Invalid Google Sheets URL. "
            "Expected format: https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        )
    return match.group(1)


def read_master_table(sheet_url: str, worksheet_name: str = None) -> pd.DataFrame:
    """
    Load the master timetable from a Google Sheet into a Pandas DataFrame.

    Parameters
    ----------
    sheet_url : str
        Full Google Sheets URL.
    worksheet_name : str, optional
        Name of the specific worksheet/tab to read. Defaults to the first sheet.

    Returns
    -------
    pd.DataFrame
        Master table with columns normalised to lowercase.

    The expected columns are:
        s_no, roll_no, name, batch, day, slot, period, staff, helper
    (Column names are normalised: stripped, lowercased, spaces → underscores)
    """
    client = _get_client()
    sheet_id = extract_sheet_id(sheet_url)
    spreadsheet = client.open_by_key(sheet_id)

    if worksheet_name:
        worksheet = spreadsheet.worksheet(worksheet_name)
    else:
        worksheet = spreadsheet.sheet1

    # Get all values including header row
    records = worksheet.get_all_records()
    if not records:
        raise ValueError("The sheet appears to be empty or has no data rows.")

    df = pd.DataFrame(records)

    # Normalise column names: strip, lowercase, replace spaces with underscores
    df.columns = [
        col.strip().lower().replace(" ", "_").replace(".", "")
        for col in df.columns
    ]

    return df


def get_available_slots_from_sheet(
    sheet_url: str,
    day_filter: str = "",
    worksheet_name: str = None,
) -> list[str]:
    """
    Return a sorted list of unique time slots where at least one row
    has ``period == "-"`` (free period, matching VBA column 7 logic).

    Parameters
    ----------
    sheet_url : str
        Google Sheets URL.
    day_filter : str
        Optional day name to filter (e.g. "Monday"). Empty string = all days.
    worksheet_name : str, optional
        Specific sheet tab name.
    """
    df = read_master_table(sheet_url, worksheet_name)

    period_col = _find_column(df, ["period", "status", "availability"])
    day_col = _find_column(df, ["day"])
    slot_col = _find_column(df, ["slot", "time_slot", "timeslot", "time"])

    # Free rows: period == "-" (VBA: Trim(CStr(wsMaster.Cells(i, 7).Value)) = "-")
    mask = df[period_col].astype(str).str.strip() == "-"
    if day_filter:
        mask &= df[day_col].astype(str).str.strip().str.lower() == day_filter.lower()

    free_df = df.loc[mask]
    slots = free_df[slot_col].astype(str).str.strip().unique().tolist()
    slots = [s for s in slots if s]

    # Sort by start time (parse "HH:MM - HH:MM" style)
    slots.sort(key=_parse_slot_time)
    return slots


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str:
    """Find the first matching column name from a list of candidates."""
    for col in df.columns:
        if col in candidates:
            return col
    # Fallback: try partial matching
    for candidate in candidates:
        for col in df.columns:
            if candidate in col:
                return col
    raise KeyError(
        f"Could not find a column matching any of {candidates}. "
        f"Available columns: {list(df.columns)}"
    )


def _parse_slot_time(slot: str) -> float:
    """
    Parse a time-slot string (e.g. "09:00 - 10:00") into a sortable float.
    Mirrors the VBA ParseTime function.
    """
    try:
        start_str = slot.split("-")[0].strip()
        parts = start_str.replace(".", ":").split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        return hours + minutes / 60.0
    except (ValueError, IndexError):
        return 9999.0  # Push unparseable slots to the end
