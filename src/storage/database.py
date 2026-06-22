import json
import hashlib
import logging
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials

from config.settings import SPREADSHEET_ID, GOOGLE_CREDENTIALS_JSON, GOOGLE_CREDENTIALS_PATH

log = logging.getLogger(__name__)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Column order — determines layout in Google Sheet
COLUMNS = [
    "job_hash",         # A  internal dedup key (must stay first)
    "role_name",        # B  normalised role level
    "title",            # C  exact title from posting
    "company",          # D
    "location",         # E
    "salary",           # F
    "fit_tier",         # G
    "ats_score",        # H
    "skills_required",  # I
    "matched_keywords", # J
    "missing_keywords", # K
    "ats_summary",      # L
    "url",              # M
    "source",           # N
    "date_posted",      # O
    "date_fetched",     # P
    "description",      # Q  long text, kept at end
    "emailed",          # R  internal flag
]

# Map column name → letter (auto-derived from COLUMNS order)
_COL = {col: chr(ord("A") + i) for i, col in enumerate(COLUMNS)}

_spreadsheet: gspread.Spreadsheet | None = None
_worksheet: gspread.Worksheet | None = None


def _today_tab() -> str:
    """Worksheet name for the current run, e.g. '2026-06-22'."""
    return datetime.now().strftime("%Y-%m-%d")


def _get_spreadsheet() -> gspread.Spreadsheet:
    global _spreadsheet
    if _spreadsheet is not None:
        return _spreadsheet
    if GOOGLE_CREDENTIALS_JSON:
        creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
        client = gspread.service_account_from_dict(creds_info)
    else:
        client = gspread.service_account(filename=GOOGLE_CREDENTIALS_PATH)
    _spreadsheet = client.open_by_key(SPREADSHEET_ID)
    return _spreadsheet


def _get_sheet() -> gspread.Worksheet:
    """Return today's date-named worksheet, creating it (with headers) if missing."""
    global _worksheet
    name = _today_tab()
    if _worksheet is not None and _worksheet.title == name:
        return _worksheet

    ss = _get_spreadsheet()
    try:
        ws = ss.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=name, rows=2000, cols=len(COLUMNS))
        ws.insert_row(COLUMNS, 1)
        log.info(f"Created new sheet tab: {name}")
    _worksheet = ws
    return ws


def make_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def init_db():
    """Ensure today's sheet exists and its header row matches current COLUMNS."""
    sheet = _get_sheet()
    if sheet.row_values(1) != COLUMNS:
        sheet.clear()
        sheet.insert_row(COLUMNS, 1)
        log.info(f"Sheet '{sheet.title}' headers initialised.")


def _job_to_row(job: dict) -> list:
    desc = (job.get("description") or "")[:49000]  # Sheets 50k char cell limit
    return [
        job.get("job_hash", ""),
        job.get("role_name", ""),
        job.get("title", ""),
        job.get("company", ""),
        job.get("location", ""),
        job.get("salary", ""),
        "",   # fit_tier   — filled by ATS scorer
        "",   # ats_score  — filled by ATS scorer
        "",   # skills_required — filled by ATS scorer
        "",   # matched_keywords
        "",   # missing_keywords
        "",   # ats_summary
        job.get("url", ""),
        job.get("source", ""),
        job.get("date_posted", ""),
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        desc,
        "0",  # emailed
    ]


def insert_jobs_batch(jobs: list[dict]) -> int:
    """Insert multiple jobs at once, skipping duplicates. Returns count of new rows."""
    if not jobs:
        return 0
    sheet = _get_sheet()
    existing = set(sheet.col_values(1)[1:])  # all job_hashes, skip header

    new_rows = []
    for job in jobs:
        if job["job_hash"] in existing:
            continue
        existing.add(job["job_hash"])
        new_rows.append(_job_to_row(job))

    if new_rows:
        sheet.append_rows(new_rows, value_input_option="RAW")

    return len(new_rows)


def insert_job(job: dict) -> bool:
    return insert_jobs_batch([job]) == 1


def update_ats(job_hash: str, score: int, matched: str, missing: str,
               tier: str, summary: str, skills: str = ""):
    """Update ATS columns G–L for a job row."""
    sheet = _get_sheet()
    try:
        cell = sheet.find(job_hash, in_column=1)
        row = cell.row
        # Columns G→L: fit_tier, ats_score, skills_required, matched, missing, summary
        start = f"{_COL['fit_tier']}{row}"
        end   = f"{_COL['ats_summary']}{row}"
        sheet.update(f"{start}:{end}",
                     [[tier, score, skills, matched, missing, summary]],
                     value_input_option="RAW")
    except gspread.exceptions.CellNotFound:
        log.warning(f"update_ats: {job_hash} not found in sheet.")


def _values_to_dicts(values: list[list]) -> list[dict]:
    if len(values) < 2:
        return []
    headers = values[0]
    return [
        {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
        for row in values[1:]
    ]


def _read_all() -> list[dict]:
    """Read today's sheet as dicts (used by the same-run scoring/email pipeline)."""
    return _values_to_dicts(_get_sheet().get_all_values())


def _read_all_tabs() -> list[dict]:
    """Read every date-named tab as dicts (used by the dashboard for history)."""
    rows: list[dict] = []
    for ws in _get_spreadsheet().worksheets():
        try:
            rows.extend(_values_to_dicts(ws.get_all_values()))
        except Exception as e:
            log.debug(f"Skipping tab '{ws.title}': {e}")
    return rows


def get_unscored_jobs(limit: int = 100) -> list[dict]:
    return [
        r for r in _read_all()
        if not str(r.get("ats_score", "")).strip()
    ][:limit]


def get_unemailed_jobs() -> list[dict]:
    return [
        r for r in _read_all()
        if str(r.get("emailed", "0")) == "0"
        and r.get("fit_tier") in ("Strong", "Maybe")
        and str(r.get("ats_score", "")).strip()
    ]


def mark_emailed(job_hashes: list[str]):
    sheet = _get_sheet()
    updates = []
    for h in job_hashes:
        try:
            cell = sheet.find(h, in_column=1)
            updates.append({"range": f"{_COL['emailed']}{cell.row}", "values": [["1"]]})
        except gspread.exceptions.CellNotFound:
            pass
    if updates:
        sheet.batch_update(updates, value_input_option="RAW")


def get_all_jobs(days: int = 7) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = []
    for r in _read_all_tabs():
        try:
            fetched = datetime.strptime(str(r.get("date_fetched", "")), "%Y-%m-%d %H:%M:%S")
            if fetched >= cutoff:
                result.append(r)
        except (ValueError, TypeError):
            result.append(r)
    result.sort(key=lambda x: int(x.get("ats_score") or 0), reverse=True)
    return result


def get_job_by_hash(job_hash: str) -> dict | None:
    for r in _read_all_tabs():
        if r.get("job_hash") == job_hash:
            return r
    return None
