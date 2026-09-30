"""
Job Hunter — daily runner.

Usage:
  python main.py          # fetch + score + email
  python main.py --fetch  # fetch + score (no email)
  python main.py --score  # score pending jobs only
  python main.py --email  # send email digest only
"""

import sys
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

from src.storage.database import init_db, insert_jobs_batch
from src.fetchers import discovery, workday, smartrecruiters, greenhouse, lever
from src.analyzer.ats_scorer import score_pending_jobs
from src.notifier.email_digest import send_digest


def fetch_all() -> tuple[int, int]:
    new_count = 0
    found_count = 0

    # Primary high-volume: query curated Greenhouse company boards directly
    log.info("── Greenhouse (direct company boards) ──")
    try:
        jobs = greenhouse.fetch()
        found_count += len(jobs)
        new  = insert_jobs_batch(jobs)
        log.info(f"  Greenhouse: {len(jobs)} found, {new} new")
        new_count += new
    except Exception as e:
        log.error(f"Greenhouse fetcher crashed: {e}")

    # Primary high-volume: query curated Lever company boards directly
    log.info("── Lever (direct company boards) ──")
    try:
        jobs = lever.fetch()
        found_count += len(jobs)
        new  = insert_jobs_batch(jobs)
        log.info(f"  Lever: {len(jobs)} found, {new} new")
        new_count += new
    except Exception as e:
        log.error(f"Lever fetcher crashed: {e}")

    # Supplemental: LinkedIn/Indeed discovery → auto-detect career page ATS
    log.info("── Discovery (LinkedIn + Indeed → career pages) ──")
    try:
        jobs = discovery.fetch()
        found_count += len(jobs)
        new  = insert_jobs_batch(jobs)
        log.info(f"  Discovery: {len(jobs)} total, {new} new")
        new_count += new
    except Exception as e:
        log.error(f"Discovery fetcher crashed: {e}")

    # Supplemental: hardcoded enterprise career pages not on Greenhouse/Lever
    log.info("── Workday (banks / enterprises) ──")
    try:
        jobs = workday.fetch()
        found_count += len(jobs)
        new  = insert_jobs_batch(jobs)
        log.info(f"  Workday: {len(jobs)} found, {new} new")
        new_count += new
    except Exception as e:
        log.error(f"Workday fetcher crashed: {e}")

    log.info("── SmartRecruiters ──")
    try:
        jobs = smartrecruiters.fetch()
        found_count += len(jobs)
        new  = insert_jobs_batch(jobs)
        log.info(f"  SmartRecruiters: {len(jobs)} found, {new} new")
        new_count += new
    except Exception as e:
        log.error(f"SmartRecruiters fetcher crashed: {e}")

    if found_count == 0:
        raise RuntimeError("All job sources returned zero results.")
    return new_count, found_count


def run(do_fetch=True, do_score=True, do_email=True):
    init_db()

    if do_fetch:
        new, found = fetch_all()
        log.info(f"Total jobs found: {found}; new jobs inserted: {new}")
        # Pulling new data always triggers scoring so no job is left unscored.
        do_score = True

    if do_score:
        log.info("── Scoring jobs with GROQ ──")
        score_pending_jobs()

    if do_email:
        log.info("── Sending email digest ──")
        send_digest()

    log.info("✅ Done.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--fetch" in args:
        run(do_fetch=True, do_score=False, do_email=False)
    elif "--score" in args:
        run(do_fetch=False, do_score=True, do_email=False)
    elif "--email" in args:
        run(do_fetch=False, do_score=False, do_email=True)
    else:
        run()
