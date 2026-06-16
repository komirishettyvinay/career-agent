import pandas as pd
from jobspy import scrape_jobs
from config.settings import SEARCH_KEYWORDS, LOCATION, HOURS_OLD, MAX_JOBS_PER_SOURCE
from src.storage.database import make_hash

import logging
log = logging.getLogger(__name__)


def _safe(val) -> str:
    """Convert pandas value to string, treating NA/NaN/None as empty string."""
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    return "" if s in ("nan", "None", "<NA>", "NaT") else s


def _normalize_role(title: str) -> str:
    t = title.lower()
    if any(x in t for x in ["senior", "sr.", "sr ", "level iii", "level 3"]):
        return "Senior Data Engineer"
    if any(x in t for x in ["lead", "principal", "staff", "architect"]):
        return "Lead Data Engineer"
    if any(x in t for x in ["junior", "jr.", "jr ", "entry level", "level i "]):
        return "Junior Data Engineer"
    if any(x in t for x in ["manager", "director", "head of"]):
        return "Data Engineering Manager"
    return "Data Engineer"


def _format_salary(row) -> str:
    min_a    = _safe(row.get("min_amount"))
    max_a    = _safe(row.get("max_amount"))
    currency = _safe(row.get("currency")) or "CAD"
    interval = _safe(row.get("interval")) or "year"
    if min_a and max_a:
        return f"{currency} {min_a}–{max_a}/{interval}"
    if min_a:
        return f"{currency} {min_a}+/{interval}"
    return ""


def fetch() -> list[dict]:
    jobs = []
    for keyword in SEARCH_KEYWORDS:
        try:
            df: pd.DataFrame = scrape_jobs(
                site_name=["linkedin"],
                search_term=keyword,
                location=LOCATION,
                results_wanted=MAX_JOBS_PER_SOURCE,
                hours_old=HOURS_OLD,
                verbose=0,
            )
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                url = _safe(row.get("job_url_direct")) or _safe(row.get("job_url"))
                if not url:
                    continue
                title = _safe(row.get("title"))
                jobs.append({
                    "job_hash":   make_hash(url),
                    "role_name":  _normalize_role(title),
                    "title":      title,
                    "company":    _safe(row.get("company")),
                    "location":   _safe(row.get("location")),
                    "salary":     _format_salary(row),
                    "url":        url,
                    "description": _safe(row.get("description")),
                    "source":     "linkedin",
                    "date_posted": _safe(row.get("date_posted")),
                })
        except Exception as e:
            log.warning(f"LinkedIn fetch failed for '{keyword}': {e}")

    # dedupe within this batch by hash
    seen, unique = set(), []
    for j in jobs:
        if j["job_hash"] not in seen:
            seen.add(j["job_hash"])
            unique.append(j)
    return unique
