"""
MCP (Model Context Protocol) server — exposes tools for AI agent interaction.

Architecture: MCP → Python Tool → Google Sheets API
(MCP never connects directly to Google Sheets)

Tools exposed:
    1. read_master_table(sheet_url)       — Load master timetable
    2. generate_slot_allocation(...)      — Run the allocation engine
    3. export_slot_results(results, file) — Export results to Excel

Usage:
    python -m app.mcp.server
"""
import io
import json
import os
import sys

# Add project root to path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from mcp.server.fastmcp import FastMCP
from app.services.allocation_engine import allocate

# We cannot use Flask's current_app outside request context,
# so we use gspread directly here with the creds file.
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# ── Initialise MCP server ──
mcp = FastMCP(
    "CRC Portal Slot Allocator",
    description="AI-accessible tools for reading timetables and generating GD-PI slot allocations.",
)

# ── Config ──
CREDS_FILE = os.getenv(
    "GOOGLE_CREDS_FILE",
    os.path.join(os.path.dirname(__file__), "..", "..", "slotallocator-d352c8aaa512.json"),
)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_gspread_client() -> gspread.Client:
    """Create authorised gspread client."""
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def _extract_sheet_id(url: str) -> str:
    """Extract spreadsheet ID from URL."""
    import re
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError("Invalid Google Sheets URL.")
    return match.group(1)


# ── Tool 1: Read Master Table ──

@mcp.tool()
def read_master_table(sheet_url: str) -> str:
    """
    Read the master timetable from a Google Sheet.

    Args:
        sheet_url: Full Google Sheets URL
            (e.g. https://docs.google.com/spreadsheets/d/{id}/edit)

    Returns:
        JSON string containing the timetable data with columns:
        sno, roll_no, name, batch, day, time_slot, status
    """
    client = _get_gspread_client()
    sheet_id = _extract_sheet_id(sheet_url)
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.sheet1

    records = worksheet.get_all_records()
    if not records:
        return json.dumps({"error": "Sheet is empty", "data": []})

    df = pd.DataFrame(records)
    df.columns = [
        col.strip().lower().replace(" ", "_").replace(".", "")
        for col in df.columns
    ]

    return json.dumps({
        "columns": list(df.columns),
        "row_count": len(df),
        "data": df.to_dict(orient="records"),
    }, default=str)


# ── Tool 2: Generate Slot Allocation ──

@mcp.tool()
def generate_slot_allocation(
    sheet_url: str,
    roll_numbers: list[str],
    day_filter: str = "",
    panel_count: int = 1,
    slot_limit: int = 10,
    selected_slots: list[str] | None = None,
) -> str:
    """
    Run the slot allocation algorithm on timetable data.

    Args:
        sheet_url: Google Sheets URL containing the master timetable.
        roll_numbers: List of student roll numbers to allocate.
        day_filter: Optional day name filter (e.g. "Monday"). Empty = all days.
        panel_count: Number of parallel panels (default 1).
        slot_limit: Maximum students per panel per slot (default 10).
        selected_slots: Optional list of specific time slots to use.

    Returns:
        JSON string with allocation results containing:
        - allocated: students assigned to slots
        - not_available: students with no free slots
        - overflow: students with free slots but not allocated
        - summary: counts and statistics
    """
    # Read master table via Python (MCP → Python → Google Sheets API)
    client = _get_gspread_client()
    sheet_id = _extract_sheet_id(sheet_url)
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.sheet1
    records = worksheet.get_all_records()

    if not records:
        return json.dumps({"error": "Sheet is empty"})

    df = pd.DataFrame(records)
    df.columns = [
        col.strip().lower().replace(" ", "_").replace(".", "")
        for col in df.columns
    ]

    # Run the allocation engine
    results = allocate(
        df_master=df,
        roll_numbers=roll_numbers,
        day_filter=day_filter,
        panel_count=panel_count,
        slot_limit=slot_limit,
        selected_slots=selected_slots,
    )

    return json.dumps(results, default=str)


# ── Tool 3: Export Results ──

@mcp.tool()
def export_slot_results(results_json: str, filename: str = "allocation.xlsx") -> str:
    """
    Export allocation results to an Excel file on disk.

    Args:
        results_json: JSON string of allocation results (output from generate_slot_allocation).
        filename: Output filename (default: allocation.xlsx).

    Returns:
        JSON string with the path to the saved file.
    """
    from app.routes.allocator import _generate_excel

    results = json.loads(results_json)
    panel_count = 1  # Default; could be passed as param

    wb = _generate_excel(results, panel_count)

    # Save to current directory
    save_path = os.path.abspath(filename)
    wb.save(save_path)

    return json.dumps({
        "status": "success",
        "file_path": save_path,
        "message": f"Results exported to {save_path}",
    })


# ── Entry point ──

if __name__ == "__main__":
    mcp.run()
