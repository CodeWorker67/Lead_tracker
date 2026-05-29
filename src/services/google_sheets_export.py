from __future__ import annotations

from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from loguru import logger
from sqlalchemy.orm import Session

from config import settings
from services.google_sheets_rows import build_sheet_rows, parse_spreadsheet_id
from services.sources_stats import get_sources_stats

BOT_EXPORTS: tuple[tuple[int, str | None], ...] = (
    (7412940598, settings.google_path_zoomer),
    (8159162956, settings.google_path_open21),
    (8713389924, settings.google_path_friends),
)

SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)


def resolve_service_account_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_file():
        return candidate

    repo_root = Path(__file__).resolve().parent.parent.parent
    for base in (repo_root, Path("/app/repo")):
        resolved = base / path
        if resolved.is_file():
            return resolved

    raise FileNotFoundError(f"Google service account file not found: {path}")


def _get_gspread_client() -> gspread.Client:
    key_path = resolve_service_account_path(settings.google_service_account_file)
    creds = Credentials.from_service_account_file(str(key_path), scopes=SCOPES)
    return gspread.authorize(creds)


def export_bot_to_sheet(
    session: Session,
    bot_id: int,
    spreadsheet_ref: str,
    *,
    client: gspread.Client | None = None,
) -> None:
    sources_data = get_sources_stats(session, bot_id=bot_id)
    rows = build_sheet_rows(sources_data)

    spreadsheet_id = parse_spreadsheet_id(spreadsheet_ref)
    gc = client or _get_gspread_client()
    spreadsheet = gc.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.sheet1
    worksheet.clear()
    worksheet.update(rows, value_input_option="USER_ENTERED")
    logger.info(
        "Google Sheets export done: bot_id={} spreadsheet={} rows={}",
        bot_id,
        spreadsheet_id,
        len(rows),
    )


def export_all_configured_bots() -> None:
    if not settings.google_exports_enabled:
        return

    from admin.db import SessionLocal

    client = _get_gspread_client()
    session = SessionLocal()
    try:
        for bot_id, spreadsheet_ref in BOT_EXPORTS:
            if not spreadsheet_ref:
                continue
            export_bot_to_sheet(session, bot_id, spreadsheet_ref, client=client)
    finally:
        session.close()
