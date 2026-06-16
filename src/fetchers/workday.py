import requests
from config.settings import SEARCH_KEYWORDS, LOCATION
from src.storage.database import make_hash

import logging
log = logging.getLogger(__name__)

# (display_name, tenant, job_site_id, wd_instance)
WORKDAY_COMPANIES = [
    # ── Canadian Banks ─────────────────────────────────────────────────────
    ("RBC",        "rbc",        "RBC_Careers",                   3),
    ("TD Bank",    "td",         "TD_Bank_Careers",               3),
    ("Scotiabank", "scotiabank", "Scotia_External_Career_Site",   3),
    ("BMO",        "bmo",        "External_Career_Site",          3),
    ("CIBC",       "cibc",       "External",                      3),
    ("Desjardins", "desjardins", "desjardins_careers",            3),
    # ── Canadian Telcos ────────────────────────────────────────────────────
    ("Telus",      "telus",      "TCareerSite",                   3),
    ("Rogers",     "rogers",     "External",                      3),
    ("Bell",       "bce",        "en_CA",                         3),
    # ── Canadian Enterprises ───────────────────────────────────────────────
    ("Loblaw",     "loblaw",     "LCL_Careers",                   3),
    ("Manulife",   "manulife",   "MFC",                           5),
    ("Sun Life",   "sunlife",    "Sunlife",                       3),
    ("TELUS Health","telushealth","TH_Careers",                   3),
    # ── Global tech with Canadian offices ─────────────────────────────────
    ("SAP",        "sap",        "SAP",                           3),
    ("Oracle",     "oracle",     "oracle_careers",                3),
    ("Workiva",    "workiva",    "careers",                       3),
    ("Ceridian",   "ceridian",   "CeridianCareers",               3),
    ("OpenText",   "opentext",   "opentext_careers",              3),
]

_CANADA_HINTS = {
    "canada", "toronto", "vancouver", "montreal", "calgary", "ottawa",
    "edmonton", "winnipeg", "quebec", "remote", "anywhere", "worldwide",
    "global", "hybrid",
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
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "JobHunterBot/1.0",
    })

    for display_name, tenant, job_site, wd_num in WORKDAY_COMPANIES:
        api_url = (
            f"https://{tenant}.wd{wd_num}.myworkdayjobs.com"
            f"/wday/cxs/{tenant}/{job_site}/jobs"
        )
        try:
            resp = session.post(
                api_url,
                json={"appliedFacets": {}, "limit": 20, "offset": 0,
                      "searchText": "data engineer"},
                timeout=12,
            )
            if resp.status_code != 200:
                continue

            for item in resp.json().get("jobPostings", []):
                title    = item.get("title", "")
                location = item.get("locationsText", "")

                if not _is_data_role(title):
                    continue
                if not _is_canadian(location):
                    continue

                ext_path = item.get("externalPath", "")
                if not ext_path:
                    continue

                apply_url = (
                    f"https://{tenant}.wd{wd_num}.myworkdayjobs.com"
                    f"/en-US/{job_site}{ext_path}"
                )

                posted = item.get("postedOn", "")
                if posted:
                    posted = posted[:10]

                jobs.append({
                    "job_hash":   make_hash(apply_url),
                    "role_name":  _normalize_role(title),
                    "title":      title,
                    "company":    display_name,
                    "location":   location or LOCATION,
                    "salary":     "",
                    "url":        apply_url,
                    "description": "",
                    "source":     "workday",
                    "date_posted": posted,
                })

        except Exception as e:
            log.debug(f"Workday '{display_name}' failed: {e}")

    return jobs
