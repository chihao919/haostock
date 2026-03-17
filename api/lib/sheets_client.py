"""Google Sheets client using Service Account for Python backend.

Mirrors the readSheet/readAllSheets pattern from mcp-server/index.js.
Credentials: GOOGLE_SA_KEY_JSON env var (JSON string) or GOOGLE_SA_KEY file path.
Spreadsheet: PORTFOLIO_SHEET_ID env var.
"""

import os
import json

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_sheets_service = None


def _get_credentials() -> Credentials:
    """Load Service Account credentials from env var or file."""
    json_str = os.environ.get("GOOGLE_SA_KEY_JSON", "")
    if json_str:
        info = json.loads(json_str)
        return Credentials.from_service_account_info(info, scopes=_SCOPES)

    key_path = os.environ.get(
        "GOOGLE_SA_KEY",
        os.path.expanduser("~/.config/claude-sheets/credentials.json"),
    )
    return Credentials.from_service_account_file(key_path, scopes=_SCOPES)


def get_sheets_service():
    """Return a cached google sheets service instance."""
    global _sheets_service
    if _sheets_service is None:
        creds = _get_credentials()
        _sheets_service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return _sheets_service


def _get_spreadsheet_id(override: str | None = None) -> str:
    """Return spreadsheet ID from override or env."""
    return override or os.environ.get("PORTFOLIO_SHEET_ID", "")


def read_sheet(name: str, spreadsheet_id: str | None = None) -> list[dict]:
    """Read a single sheet tab, return list of dicts (header row = keys)."""
    svc = get_sheets_service()
    sid = _get_spreadsheet_id(spreadsheet_id)
    res = svc.spreadsheets().values().get(
        spreadsheetId=sid, range=f"{name}!A1:Z1000"
    ).execute()
    rows = res.get("values", [])
    if len(rows) <= 1:
        return []
    headers = rows[0]
    return [
        {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
        for row in rows[1:]
    ]


def read_all_sheets(
    sheet_names: list[str] | None = None,
    spreadsheet_id: str | None = None,
) -> dict[str, list[dict]]:
    """Batch-read multiple sheets. Returns {sheet_name: [rows]}."""
    if sheet_names is None:
        sheet_names = ["US_Stocks", "TW_Stocks", "Options", "Bonds", "Loans", "Income", "Settings"]
    svc = get_sheets_service()
    sid = _get_spreadsheet_id(spreadsheet_id)
    ranges = [f"{s}!A1:Z1000" for s in sheet_names]
    res = svc.spreadsheets().values().batchGet(
        spreadsheetId=sid, ranges=ranges
    ).execute()
    result = {}
    for vr in res.get("valueRanges", []):
        name = vr["range"].split("!")[0].replace("'", "")
        rows = vr.get("values", [])
        if len(rows) <= 1:
            result[name] = []
            continue
        headers = rows[0]
        result[name] = [
            {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
            for row in rows[1:]
        ]
    return result


def append_rows(sheet: str, rows: list[list[str]], spreadsheet_id: str | None = None) -> int:
    """Append rows to a sheet. Returns number of rows appended."""
    svc = get_sheets_service()
    sid = _get_spreadsheet_id(spreadsheet_id)
    svc.spreadsheets().values().append(
        spreadsheetId=sid,
        range=f"{sheet}!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()
    return len(rows)


def update_sheet(sheet: str, rows: list[list[str]], spreadsheet_id: str | None = None) -> int:
    """Overwrite all data rows (below header) in a sheet."""
    svc = get_sheets_service()
    sid = _get_spreadsheet_id(spreadsheet_id)
    # Clear existing data rows
    svc.spreadsheets().values().clear(
        spreadsheetId=sid, range=f"{sheet}!A2:Z1000", body={}
    ).execute()
    if rows:
        svc.spreadsheets().values().update(
            spreadsheetId=sid,
            range=f"{sheet}!A2",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()
    return len(rows)


# --- Users sheet helpers ---

_USERS_SHEET = "Users"
_USER_HEADERS = [
    "email", "name", "line_channel_token", "line_user_id",
    "trello_api_key", "trello_token", "trello_board_id", "trello_list_id",
    "stop_loss_spec", "stop_loss_invest", "cc_pipeline", "spec_tickers",
    "spreadsheet_id", "active",
]


def get_all_users(spreadsheet_id: str | None = None) -> list[dict]:
    """Read all users from the Users sheet."""
    return read_sheet(_USERS_SHEET, spreadsheet_id)


def get_active_users(spreadsheet_id: str | None = None) -> list[dict]:
    """Return only active users."""
    return [u for u in get_all_users(spreadsheet_id) if u.get("active", "").lower() == "true"]


def find_user_by_email(email: str, spreadsheet_id: str | None = None) -> dict | None:
    """Find a user row by email. Returns None if not found."""
    for user in get_all_users(spreadsheet_id):
        if user.get("email", "").lower() == email.lower():
            return user
    return None


def _user_to_row(user: dict) -> list[str]:
    """Convert user dict to sheet row in header order."""
    return [str(user.get(h, "")) for h in _USER_HEADERS]


def upsert_user(user_data: dict, spreadsheet_id: str | None = None) -> str:
    """Insert or update a user row by email. Returns 'created' or 'updated'."""
    svc = get_sheets_service()
    sid = _get_spreadsheet_id(spreadsheet_id)

    # Ensure Users sheet exists with headers
    try:
        svc.spreadsheets().values().get(
            spreadsheetId=sid, range=f"{_USERS_SHEET}!A1:N1"
        ).execute()
    except Exception:
        # Create sheet
        try:
            svc.spreadsheets().batchUpdate(
                spreadsheetId=sid,
                body={"requests": [{"addSheet": {"properties": {"title": _USERS_SHEET}}}]},
            ).execute()
        except Exception:
            pass  # sheet may already exist
        svc.spreadsheets().values().update(
            spreadsheetId=sid,
            range=f"{_USERS_SHEET}!A1",
            valueInputOption="RAW",
            body={"values": [_USER_HEADERS]},
        ).execute()

    # Read existing users
    res = svc.spreadsheets().values().get(
        spreadsheetId=sid, range=f"{_USERS_SHEET}!A1:Z1000"
    ).execute()
    all_rows = res.get("values", [])
    headers = all_rows[0] if all_rows else _USER_HEADERS
    data_rows = all_rows[1:] if len(all_rows) > 1 else []

    email = user_data.get("email", "").lower()
    email_idx = headers.index("email") if "email" in headers else 0

    # Find existing row
    for i, row in enumerate(data_rows):
        row_email = row[email_idx] if email_idx < len(row) else ""
        if row_email.lower() == email:
            # Update existing row
            new_row = _user_to_row(user_data)
            row_num = i + 2  # 1-indexed, skip header
            svc.spreadsheets().values().update(
                spreadsheetId=sid,
                range=f"{_USERS_SHEET}!A{row_num}",
                valueInputOption="RAW",
                body={"values": [new_row]},
            ).execute()
            return "updated"

    # Append new user
    append_rows(_USERS_SHEET, [_user_to_row(user_data)], spreadsheet_id)
    return "created"


def mask_token(token: str, visible: int = 4) -> str:
    """Mask a token, showing only the last N characters."""
    if not token or len(token) <= visible:
        return token
    return "*" * (len(token) - visible) + token[-visible:]
