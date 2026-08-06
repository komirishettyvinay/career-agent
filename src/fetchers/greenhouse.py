import requests
from src.fetchers._descriptions import html_to_text
from config.settings import GREENHOUSE_COMPANIES, LOCATION
from src.fetchers._filters import is_canadian as _is_canadian, is_data_role as _is_data_role
from src.storage.database import make_hash

import logging
log = logging.getLogger(__name__)

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
DETAIL_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}"


def _get_description(session: requests.Session, slug: str, job: dict) -> str:
    """Greenhouse list responses omit content; retrieve the selected job."""
    job_id = job.get("id")
    if not job_id:
        return ""
    try:
        response = session.get(
            DETAIL_URL.format(slug=slug, job_id=job_id), timeout=10
        )
        if response.status_code == 200:
            return html_to_text(response.json().get("content", ""))
    except requests.RequestException:
        pass
    return ""


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
                    "description": _get_description(session, slug, job),
                    "source":     "greenhouse",
                    "date_posted": job.get("updated_at", "")[:10],
                })
        except Exception as e:
            log.debug(f"Greenhouse '{slug}' failed: {e}")

    return jobs
