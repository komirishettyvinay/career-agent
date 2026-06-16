"""
Hybrid discovery fetcher.

Step 1 — Search LinkedIn + Indeed for "Data Engineer" in Canada to discover
          which companies are actively hiring right now.

Step 2 — For each company found, auto-detect whether they use Greenhouse or
          Lever by probing common slug variants.  If found → pull full job
          details from the company's own career page API.

Step 3 — For companies that aren't on a known ATS, fall back to the direct
          apply URL that python-jobspy extracted (often the company's own site).
"""

import re
import time
import logging

import pandas as pd
import requests
from jobspy import scrape_jobs

from config.settings import SEARCH_KEYWORDS, LOCATION, HOURS_OLD, MAX_JOBS_PER_SOURCE
from src.storage.database import make_hash

log = logging.getLogger(__name__)

_CANADA_HINTS = {
    "canada", "toronto", "vancouver", "montreal", "calgary", "ottawa",
    "edmonton", "winnipeg", "quebec", "remote", "anywhere", "worldwide", "global",
}
_EXCLUDE_LOCS = {
    "united states", "usa", "us only", "london", "uk only",
    "australia", "india", "germany", "france", "brazil",
}
_KW_LOWER = [k.lower() for k in SEARCH_KEYWORDS]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe(val) -> str:
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    return "" if s in ("nan", "None", "<NA>", "NaT") else s


def _is_data_role(title: str) -> bool:
    return any(kw in title.lower() for kw in _KW_LOWER)


def _is_canadian(location: str) -> bool:
    if not location:
        return True
    loc = location.lower()
    if any(ex in loc for ex in _EXCLUDE_LOCS):
        return False
    return any(h in loc for h in _CANADA_HINTS)


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


def _slugs(company_name: str) -> list[str]:
    """Generate candidate ATS slugs from a company display name."""
    clean = re.sub(r"[^a-z0-9\s]", "", company_name.lower()).strip()
    hyphen = clean.replace(" ", "-")
    nospace = clean.replace(" ", "")
    variants = [hyphen, nospace]
    # strip common suffixes that companies drop from their ATS slug
    for suffix in ["-inc", "-corp", "-ltd", "-llc", "-co",
                   "-technologies", "-solutions", "-canada", "-ai"]:
        if hyphen.endswith(suffix):
            variants.append(hyphen[: -len(suffix)])
    return list(dict.fromkeys(variants))  # dedupe, preserve order


# ── ATS probes ─────────────────────────────────────────────────────────────────

def _probe_greenhouse(slug: str, company: str) -> list[dict]:
    try:
        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            timeout=5,
        )
        if r.status_code != 200:
            return []
        jobs = []
        for j in r.json().get("jobs", []):
            title    = j.get("title", "")
            location = j.get("location", {}).get("name", "")
            url      = j.get("absolute_url", "")
            if not url or not _is_data_role(title) or not _is_canadian(location):
                continue
            jobs.append({
                "job_hash":    make_hash(url),
                "role_name":   _normalize_role(title),
                "title":       title,
                "company":     company,
                "location":    location or LOCATION,
                "salary":      "",
                "url":         url,
                "description": "",
                "source":      f"greenhouse/{slug}",
                "date_posted": j.get("updated_at", "")[:10],
            })
        return jobs
    except Exception:
        return []


def _probe_lever(slug: str, company: str) -> list[dict]:
    try:
        r = requests.get(
            f"https://api.lever.co/v0/postings/{slug}?mode=json",
            timeout=5,
        )
        if r.status_code != 200 or not isinstance(r.json(), list):
            return []
        jobs = []
        for j in r.json():
            title    = j.get("text", "")
            location = j.get("categories", {}).get("location", "")
            url      = j.get("hostedUrl", "")
            if not url or not _is_data_role(title) or not _is_canadian(location):
                continue
            desc = "\n".join(
                s.get("text", "")
                for s in j.get("descriptionBody", {}).get("content", [])
            )
            jobs.append({
                "job_hash":    make_hash(url),
                "role_name":   _normalize_role(title),
                "title":       title,
                "company":     company,
                "location":    location or LOCATION,
                "salary":      "",
                "url":         url,
                "description": desc.strip(),
                "source":      f"lever/{slug}",
                "date_posted": "",
            })
        return jobs
    except Exception:
        return []


def _find_on_ats(company: str) -> list[dict]:
    """
    Try Greenhouse then Lever for a company.
    Returns jobs from the first ATS that responds, or [] if neither found.
    """
    for slug in _slugs(company):
        jobs = _probe_greenhouse(slug, company)
        if jobs:
            log.debug(f"    {company} → Greenhouse/{slug} ({len(jobs)} DE jobs)")
            return jobs
        jobs = _probe_lever(slug, company)
        if jobs:
            log.debug(f"    {company} → Lever/{slug} ({len(jobs)} DE jobs)")
            return jobs
        time.sleep(0.15)   # small pause between slug attempts
    return []


# ── Step 1: Discover companies via python-jobspy ────────────────────────────────

def _discover(sites: list[str]) -> list[dict]:
    """Scrape LinkedIn/Indeed and return raw job dicts."""
    raw = []
    for keyword in SEARCH_KEYWORDS:
        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=keyword,
                location=LOCATION,
                results_wanted=MAX_JOBS_PER_SOURCE,
                hours_old=HOURS_OLD,
                verbose=0,
            )
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                company = _safe(row.get("company"))
                url     = _safe(row.get("job_url_direct")) or _safe(row.get("job_url"))
                title   = _safe(row.get("title"))
                if not company or not url:
                    continue
                raw.append({
                    "job_hash":    make_hash(url),
                    "role_name":   _normalize_role(title),
                    "title":       title,
                    "company":     company,
                    "location":    _safe(row.get("location")),
                    "salary":      "",
                    "url":         url,
                    "description": _safe(row.get("description")),
                    "source":      "+".join(sites),
                    "date_posted": _safe(row.get("date_posted")),
                })
        except Exception as e:
            log.warning(f"Discovery scrape failed for '{keyword}': {e}")
    return raw


# ── Main entry point ───────────────────────────────────────────────────────────

def fetch() -> list[dict]:
    """
    1. Search LinkedIn + Indeed to discover companies hiring DEs in Canada.
    2. For each company, probe Greenhouse then Lever for a direct career page.
    3. Return ATS jobs where found; fall back to LinkedIn/Indeed URL otherwise.
    """
    log.info("  Step 1 — Discovering companies via LinkedIn + Indeed...")
    discovered = _discover(["linkedin", "indeed"])
    log.info(f"  Discovered {len(discovered)} job listings from {len(set(j['company'] for j in discovered))} companies")

    # Group by company to avoid duplicate ATS probes
    company_to_fallback: dict[str, list[dict]] = {}
    for j in discovered:
        company_to_fallback.setdefault(j["company"], []).append(j)

    final_jobs: list[dict] = []
    seen_hashes: set[str]  = set()

    def _add(job: dict):
        if job["job_hash"] not in seen_hashes:
            seen_hashes.add(job["job_hash"])
            final_jobs.append(job)

    log.info(f"  Step 2 — Probing career pages for {len(company_to_fallback)} companies...")
    ats_hit, fallback_count = 0, 0

    for company, fallback_jobs in company_to_fallback.items():
        ats_jobs = _find_on_ats(company)
        if ats_jobs:
            for j in ats_jobs:
                _add(j)
            ats_hit += 1
        else:
            # No ATS found → use the LinkedIn/Indeed URL directly
            for j in fallback_jobs:
                _add(j)
            fallback_count += 1
        time.sleep(0.2)  # be polite to ATS APIs

    log.info(
        f"  Step 2 done — {ats_hit} companies on Greenhouse/Lever "
        f"(career page links), {fallback_count} using LinkedIn/Indeed URL"
    )
    return final_jobs
