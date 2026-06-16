import requests
from config.settings import GREENHOUSE_COMPANIES, SEARCH_KEYWORDS, LOCATION
from src.storage.database import make_hash

import logging
log = logging.getLogger(__name__)

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
_CANADA_HINTS = {
    "canada", "toronto", "vancouver", "montreal", "calgary",
    "ottawa", "edmonton", "winnipeg", "quebec", "remote",
    "anywhere", "worldwide", "global",
}
_EXCLUDE_LOCATIONS = {
    "united states", "usa", "us only", "london", "uk only",
    "australia", "india", "germany", "france", "brazil",
}
_KW_LOWER = [k.lower() for k in SEARCH_KEYWORDS]


def _is_canadian(location: str) -> bool:
    if not location:
        return True
    loc = location.lower()
    if any(ex in loc for ex in _EXCLUDE_LOCATIONS):
        return False
    return any(hint in loc for hint in _CANADA_HINTS)


def _is_data_role(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in _KW_LOWER)


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


def fetch() -> list[dict]:
    jobs = []
    session = requests.Session()
    session.headers.update({"User-Agent": "JobHunterBot/1.0"})

    for slug in GREENHOUSE_COMPANIES:
        try:
            resp = session.get(BASE_URL.format(slug=slug), timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            for job in data.get("jobs", []):
                title    = job.get("title", "")
                location = job.get("location", {}).get("name", "")

                if not _is_data_role(title):
                    continue
                if location and not _is_canadian(location):
                    continue

                url = job.get("absolute_url", "")
                if not url:
                    continue

                jobs.append({
                    "job_hash":   make_hash(url),
                    "role_name":  _normalize_role(title),
                    "title":      title,
                    "company":    slug.replace("-", " ").title(),
                    "location":   location or LOCATION,
                    "salary":     "",  # Greenhouse public API doesn't expose salary
                    "url":        url,
                    "description": "",
                    "source":     "greenhouse",
                    "date_posted": job.get("updated_at", "")[:10],
                })
        except Exception as e:
            log.debug(f"Greenhouse '{slug}' failed: {e}")

    return jobs
