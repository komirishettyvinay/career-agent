import json
import time
import logging
from groq import Groq
from config.settings import (
    GROQ_API_KEY, GROQ_MODEL, TIER_STRONG, TIER_MAYBE,
    GROQ_DAILY_TOKEN_BUDGET, SCORE_DELAY_SECONDS,
)
from src.analyzer.resume_parser import get_resume_text
from src.storage.database import get_unscored_jobs, update_ats

log = logging.getLogger(__name__)
_client: Groq | None = None

# Score the most valuable jobs first within the daily budget: real descriptions
# beat title-only, and direct career-page sources beat LinkedIn/Indeed dupes.
_SOURCE_PRIORITY = {
    "greenhouse": 3, "lever": 3,
    "smartrecruiters": 2, "workday": 2,
}


def _priority(job: dict) -> tuple:
    src = (job.get("source") or "").split("/")[0].strip().lower()
    has_desc = 1 if (job.get("description") or "").strip() else 0
    return (has_desc, _SOURCE_PRIORITY.get(src, 1))


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


SYSTEM_PROMPT = """You are an ATS (Applicant Tracking System) expert analyst.
Given a candidate resume and a job description, output ONLY valid JSON — no prose, no markdown fences.
JSON schema:
{
  "ats_score": <integer 0-100>,
  "skills_required": [<top skills/technologies required by the job, max 10 strings>],
  "matched_keywords": [<skills the candidate has that the job requires>],
  "missing_keywords": [<skills the job requires that the candidate lacks>],
  "fit_tier": <"Strong" | "Maybe" | "Skip">,
  "summary": <one sentence, max 120 chars>
}
Scoring guide:
- 75-100 → Strong (candidate clearly qualified, most must-have skills present)
- 50-74  → Maybe  (some gaps but transferable experience)
- 0-49   → Skip   (too many critical gaps)"""

USER_TEMPLATE = """RESUME:
{resume}

JOB DESCRIPTION:
{jd}"""


def _score_one(resume: str, jd: str) -> tuple[dict, int]:
    """Return (parsed result, tokens used) for one scoring call."""
    resp = _get_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(resume=resume, jd=jd[:4000])},
        ],
        temperature=0.1,
        max_tokens=600,
    )
    raw = resp.choices[0].message.content.strip()
    used = getattr(resp, "usage", None)
    tokens = used.total_tokens if used else 0
    return json.loads(raw), tokens


def _is_daily_limit(err: Exception) -> bool:
    msg = str(err).lower()
    return "tokens per day" in msg or "tpd" in msg


def score_pending_jobs():
    """Score unscored jobs, best-first, within the daily token budget."""
    resume = get_resume_text()
    jobs   = get_unscored_jobs(limit=500)

    if not jobs:
        log.info("No unscored jobs found.")
        return

    # Quality-first: highest-value jobs scored first within the budget.
    jobs.sort(key=_priority, reverse=True)
    log.info(
        f"{len(jobs)} unscored jobs. Scoring best-first within "
        f"~{GROQ_DAILY_TOKEN_BUDGET:,} tokens/day, {SCORE_DELAY_SECONDS}s apart."
    )

    used_tokens = 0
    scored = 0
    for job in jobs:
        if used_tokens >= GROQ_DAILY_TOKEN_BUDGET:
            log.info(
                f"Daily token budget reached (~{used_tokens:,} tokens). "
                f"Scored {scored}; remaining {len(jobs) - scored} will be "
                f"scored on the next run."
            )
            break

        jd = job.get("description", "").strip()
        if not jd:
            # No description available — score by title only with low confidence
            jd = (f"Job Title: {job.get('title', '')}\nCompany: {job.get('company', '')}\n"
                  f"Location: {job.get('location', '')}\n(Full description not available)")
        try:
            result, tokens = _score_one(resume, jd)
            used_tokens += tokens
            update_ats(
                job_hash=job["job_hash"],
                score=result["ats_score"],
                matched=json.dumps(result.get("matched_keywords", [])),
                missing=json.dumps(result.get("missing_keywords", [])),
                tier=result["fit_tier"],
                summary=result["summary"],
                skills=json.dumps(result.get("skills_required", [])),
            )
            scored += 1
            log.info(f"  {job['company']} | {job['title']} → {result['ats_score']}/100 ({result['fit_tier']})")
            time.sleep(SCORE_DELAY_SECONDS)
        except Exception as e:
            if _is_daily_limit(e):
                log.warning(
                    f"GROQ daily token limit hit. Scored {scored}; "
                    f"remaining {len(jobs) - scored} will be scored next run."
                )
                break
            log.warning(f"Scoring failed for {job['job_hash']}: {e}")

    log.info(f"Scoring complete: {scored} jobs scored this run.")
