import requests
from config.settings import SEARCH_KEYWORDS, LOCATION
from src.storage.database import make_hash

import logging
log = logging.getLogger(__name__)

BASE_URL = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"

SMARTRECRUITERS_COMPANIES = [
    # Canadian
    "Shopify",          "Hootsuite",       "PointClickCare",
    "Genesys",          "Mitel",           "eSentire",
    "D2L",              "Auvik",           "AlayaCare",
    "Vendasta",         "Payworks",        "Bold-Commerce",
    # Global hiring in Canada
    "Visa",             "Booking.com",     "McKesson",
    "Bosch",            "Hitachi",         "Siemens",
    "SITA",             "CGI",             "Alstom",
    "Telaria",          "AppDirect",       "Lightspeed",
    "Intact",           "iA-Financial",    "Equinix",
    "Ceridian",         "NTT-Data",        "Fujitsu",
]

_CANADA_HINTS = {
    "canada", "toronto", "vancouver", "montreal", "calgary", "ottawa",
    "edmonton", "winnipeg", "quebec", "remote", "anywhere", "worldwide",
    "global",
}
_EXCLUDE_LOCS = {
    "united states", "usa", "us only", "london", "uk only",
    "australia", "india", "germany", "france", "brazil",
}
_KW_LOWER = [k.lower() for k in SEARCH_KEYWORDS]


def _is_canadian(location: str) -> bool:
    if not location:
        return True
    loc = location.lower()
    if any(ex in loc for ex in _EXCLUDE_LOCS):
        return False
    return any(h in loc for h in _CANADA_HINTS)


def _is_data_role(title: str) -> bool:
    return any(kw in title.lower() for kw in _KW_LOWER)


def _normalize_role(title: str) -> str:
    t = title.lower()
    if any(x in t for x in ["senior", "sr.", "sr ", "level iii"]):
        return "Senior Data Engineer"
    if any(x in t for x in ["lead", "principal", "staff", "architect"]):
        return "Lead Data Engineer"
    if any(x in t for x in ["junior", "jr.", "entry level"]):
        return "Junior Data Engineer"
    if any(x in t for x in ["manager", "director"]):
        return "Data Engineering Manager"
    return "Data Engineer"


def fetch() -> list[dict]:
    jobs = []
    session = requests.Session()
    session.headers.update({"User-Agent": "JobHunterBot/1.0"})

    for slug in SMARTRECRUITERS_COMPANIES:
        try:
            resp = session.get(
                BASE_URL.format(slug=slug),
                params={"q": "data engineer", "limit": 100},
                timeout=10,
            )
            if resp.status_code != 200:
                continue

            for item in resp.json().get("content", []):
                title    = item.get("name", "")
                location = item.get("location", {})
                city     = location.get("city", "")
                country  = location.get("country", "")
                loc_str  = f"{city}, {country}".strip(", ")
                remote   = item.get("typeOfRemote", "")
                if remote in ("FULLY_REMOTE", "PARTIALLY_REMOTE"):
                    loc_str = f"Remote — {loc_str}" if loc_str else "Remote"

                if not _is_data_role(title):
                    continue
                if country and country.upper() not in ("CA", "CAN", "CANADA", ""):
                    if not _is_canadian(loc_str):
                        continue

                job_id  = item.get("id", "")
                company = item.get("company", {}).get("name", slug)
                url     = f"https://jobs.smartrecruiters.com/{slug}/{job_id}"

                jobs.append({
                    "job_hash":    make_hash(url),
                    "role_name":   _normalize_role(title),
                    "title":       title,
                    "company":     company,
                    "location":    loc_str or LOCATION,
                    "salary":      "",
                    "url":         url,
                    "description": item.get("jobAd", {}).get("sections", {})
                                      .get("jobDescription", {}).get("text", ""),
                    "source":      "smartrecruiters",
                    "date_posted": item.get("releasedDate", "")[:10],
                })

        except Exception as e:
            log.debug(f"SmartRecruiters '{slug}' failed: {e}")

    return jobs
