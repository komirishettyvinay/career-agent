import requests
from config.settings import LEVER_COMPANIES, LOCATION
from src.fetchers._filters import is_canadian as _is_canadian, is_data_role as _is_data_role
from src.storage.database import make_hash

import logging
log = logging.getLogger(__name__)

BASE_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"


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


def _format_salary(salary_range: dict) -> str:
    if not salary_range:
        return ""
    try:
        min_s = salary_range.get("min", "")
        max_s = salary_range.get("max", "")
        curr  = salary_range.get("currency", "CAD")
        if min_s and max_s:
            return f"{curr} {int(min_s):,}–{int(max_s):,}/year"
        if min_s:
            return f"{curr} {int(min_s):,}+/year"
    except (ValueError, TypeError):
        pass
    return ""


def fetch() -> list[dict]:
    jobs = []
    session = requests.Session()
    session.headers.update({"User-Agent": "JobHunterBot/1.0"})

    for slug in LEVER_COMPANIES:
        try:
            resp = session.get(BASE_URL.format(slug=slug), timeout=10)
            if resp.status_code != 200:
                continue
            postings = resp.json()
            if not isinstance(postings, list):
                continue

            for job in postings:
                title      = job.get("text", "")
                location   = job.get("categories", {}).get("location", "")

                if not _is_data_role(title):
                    continue
                if location and not _is_canadian(location):
                    continue

                url = job.get("hostedUrl", "")
                if not url:
                    continue

                # Extract description text
                desc_raw = ""
                for section in job.get("descriptionBody", {}).get("content", []):
                    desc_raw += section.get("text", "") + "\n"

                jobs.append({
                    "job_hash":   make_hash(url),
                    "role_name":  _normalize_role(title),
                    "title":      title,
                    "company":    slug.replace("-", " ").title(),
                    "location":   location or LOCATION,
                    "salary":     _format_salary(job.get("salaryRange", {})),
                    "url":        url,
                    "description": desc_raw.strip(),
                    "source":     "lever",
                    "date_posted": "",
                })
        except Exception as e:
            log.debug(f"Lever '{slug}' failed: {e}")

    return jobs
