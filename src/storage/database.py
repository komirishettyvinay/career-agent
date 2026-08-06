import json
import hashlib
import logging
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials

from config.settings import (
    SPREADSHEET_ID,
    GOOGLE_CREDENTIALS_JSON,
    GOOGLE_CREDENTIALS_PATH,
    MIN_DESCRIPTION_CHARS,
)

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
_known_hashes: set[str] | None = None
_known_jobs: dict[str, tuple[gspread.Worksheet, int, str]] = {}


def _column_values(values: list[list]) -> list[str]:
    return [row[0] if row else "" for row in values]


def _load_known_jobs():
    """Cache hash locations/descriptions with one Sheets API batch request."""
    global _known_hashes, _known_jobs
    if _known_hashes is not None:
        return
    _known_hashes = set()
    _known_jobs = {}
    spreadsheet = _get_spreadsheet()
    worksheets = spreadsheet.worksheets()
    ranges = []
    for ws in worksheets:
        title = ws.title.replace("'", "''")
        ranges.extend([
            f"'{title}'!A2:A",
            f"'{title}'!{_COL['description']}2:{_COL['description']}",
        ])
    value_ranges = spreadsheet.values_batch_get(ranges).get("valueRanges", [])
    for index, ws in enumerate(worksheets):
        hashes_range = value_ranges[index * 2].get("values", [])
        descriptions_range = value_ranges[index * 2 + 1].get("values", [])
        hashes = _column_values(hashes_range)
        descriptions = _column_values(descriptions_range)
        for offset, job_hash in enumerate(hashes, start=2):
            if not job_hash:
                continue
            description = descriptions[offset - 2] if offset - 2 < len(descriptions) else ""
            _known_hashes.add(job_hash)
            _known_jobs[job_hash] = (ws, offset, description)


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


def _format_sheet(sheet: gspread.Worksheet):
    """Keep long descriptions from expanding data rows to thousands of pixels."""
    sheet.format(
        f"A1:{_COL['emailed']}{sheet.row_count}",
        {
            "wrapStrategy": "CLIP",
            "verticalAlignment": "MIDDLE",
        },
    )
    sheet.spreadsheet.batch_update({
        "requests": [
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet.id,
                        "dimension": "ROWS",
                        "startIndex": 0,
                        "endIndex": 1,
                    },
                    "properties": {"pixelSize": 28},
                    "fields": "pixelSize",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet.id,
                        "dimension": "ROWS",
                        "startIndex": 1,
                        "endIndex": sheet.row_count,
                    },
                    "properties": {"pixelSize": 24},
                    "fields": "pixelSize",
                }
            },
        ]
    })


def init_db():
    """Ensure today's sheet exists and its header row matches current COLUMNS."""
    sheet = _get_sheet()
    if sheet.row_values(1) != COLUMNS:
        sheet.clear()
        sheet.insert_row(COLUMNS, 1)
        log.info(f"Sheet '{sheet.title}' headers initialised.")
    _format_sheet(sheet)


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
    """Insert jobs once across the workbook, rather than once per daily tab."""
    global _known_hashes
    if not jobs:
        return 0
    sheet = _get_sheet()
    _load_known_jobs()
    existing = _known_hashes

    new_rows = []
    new_jobs = []
    backfills: dict[gspread.Worksheet, list[dict]] = {}
    for job in jobs:
        if job["job_hash"] in existing:
            known = _known_jobs.get(job["job_hash"])
            new_description = (job.get("description") or "").strip()
            if known:
                ws, row, old_description = known
                if (
                    len((old_description or "").strip()) < MIN_DESCRIPTION_CHARS
                    and len(new_description) >= MIN_DESCRIPTION_CHARS
                ):
                    backfills.setdefault(ws, []).extend([
                        {
                            "range": f"{_COL['description']}{row}",
                            "values": [[new_description[:49000]]],
                        },
                        {
                            "range": f"{_COL['fit_tier']}{row}:{_COL['ats_summary']}{row}",
                            "values": [["", "", "", "", "", ""]],
                        },
                        {
                            "range": f"{_COL['emailed']}{row}",
                            "values": [["0"]],
                        },
                    ])
                    _known_jobs[job["job_hash"]] = (ws, row, new_description)
            continue
        existing.add(job["job_hash"])
        new_rows.append(_job_to_row(job))
        new_jobs.append(job)

    if new_rows:
        first_new_row = len(sheet.col_values(1)) + 1
        sheet.append_rows(new_rows, value_input_option="RAW")
        for offset, job in enumerate(new_jobs):
            _known_jobs[job["job_hash"]] = (
                sheet,
                first_new_row + offset,
                job.get("description") or "",
            )

    for ws, updates in backfills.items():
        ws.batch_update(updates, value_input_option="RAW")
    if backfills:
        log.info(
            f"Backfilled descriptions and reset stale ATS scores for "
            f"{sum(len(items) for items in backfills.values()) // 3} jobs."
        )

    return len(new_rows)


def insert_job(job: dict) -> bool:
    return insert_jobs_batch([job]) == 1


def _find_row(job_hash: str, tab: str | None = None):
    """Locate (worksheet, row) for a job_hash. Searches the given tab first,
    then falls back to every tab. Returns (None, None) if not found."""
    ss = _get_spreadsheet()
    candidates = []
    if tab:
        try:
            candidates.append(ss.worksheet(tab))
        except gspread.exceptions.WorksheetNotFound:
            pass
    candidates += [w for w in ss.worksheets() if w not in candidates]
    for ws in candidates:
        try:
            cell = ws.find(job_hash, in_column=1)
            if cell:
                return ws, cell.row
        except gspread.exceptions.CellNotFound:
            continue
    return None, None


def update_ats(job_hash: str, score: int, matched: str, missing: str,
               tier: str, summary: str, skills: str = "", tab: str | None = None):
    """Update ATS columns G–L for a job row, in whichever tab the job lives in."""
    ws, row = _find_row(job_hash, tab)
    if ws is None:
        log.warning(f"update_ats: {job_hash} not found in any tab.")
        return
    # Columns G→L: fit_tier, ats_score, skills_required, matched, missing, summary
    start = f"{_COL['fit_tier']}{row}"
    end   = f"{_COL['ats_summary']}{row}"
    ws.update(f"{start}:{end}",
              [[tier, score, skills, matched, missing, summary]],
              value_input_option="RAW")


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
    """Read every tab as dicts, tagging each row with its source tab (_sheet_tab)."""
    rows: list[dict] = []
    for ws in _get_spreadsheet().worksheets():
        try:
            for d in _values_to_dicts(ws.get_all_values()):
                d["_sheet_tab"] = ws.title
                rows.append(d)
        except Exception as e:
            log.debug(f"Skipping tab '{ws.title}': {e}")
    return rows


def get_unscored_jobs(limit: int | None = 100) -> list[dict]:
    # Scan ALL tabs so leftover unscored jobs from past days are picked up too.
    jobs = [
        r for r in _read_all_tabs()
        if not str(r.get("ats_score", "")).strip()
    ]
    return jobs if limit is None else jobs[:limit]


def get_unemailed_jobs() -> list[dict]:
    return [
        r for r in _read_all_tabs()
        if str(r.get("emailed", "0")) == "0"
        and r.get("fit_tier") in ("Strong", "Maybe")
        and str(r.get("ats_score", "")).strip()
    ]


def mark_emailed(job_hashes: list[str]):
    # Group updates per worksheet since jobs may live in different date tabs.
    per_ws: dict = {}
    for h in job_hashes:
        ws, row = _find_row(h)
        if ws is None:
            continue
        per_ws.setdefault(ws, []).append(
            {"range": f"{_COL['emailed']}{row}", "values": [["1"]]}
        )
    for ws, updates in per_ws.items():
        ws.batch_update(updates, value_input_option="RAW")


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
