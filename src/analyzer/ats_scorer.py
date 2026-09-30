import json
import time
import logging
from groq import Groq
from config.settings import (
    GROQ_API_KEY, GROQ_MODEL, TIER_STRONG, TIER_MAYBE,
    GROQ_DAILY_TOKEN_BUDGET, SCORE_DELAY_SECONDS, MIN_DESCRIPTION_CHARS,
    MIN_RESUME_CHARS,
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
        reasoning_effort="low",
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content.strip()
    used = getattr(resp, "usage", None)
    tokens = used.total_tokens if used else 0
    result = json.loads(raw)
    required = {
        "ats_score", "skills_required", "matched_keywords",
        "missing_keywords", "summary",
    }
    missing = required.difference(result)
    if missing:
        raise ValueError(f"Groq response missing fields: {sorted(missing)}")

    score = max(0, min(100, int(result["ats_score"])))
    result["ats_score"] = score
    result["fit_tier"] = (
        "Strong" if score >= TIER_STRONG
        else "Maybe" if score >= TIER_MAYBE
        else "Skip"
    )
    for field in ("skills_required", "matched_keywords", "missing_keywords"):
        if not isinstance(result[field], list):
            raise ValueError(f"Groq response field '{field}' must be a list")
    return result, tokens


def _is_daily_limit(err: Exception) -> bool:
    msg = str(err).lower()
    return (
        "tokens per day" in msg
        or "requests per day" in msg
        or "tpd" in msg
        or "rpd" in msg
    )


def _is_fatal_api_error(err: Exception) -> bool:
    status_code = getattr(err, "status_code", None)
    msg = str(err).lower()
    return status_code in (401, 403, 404) or any(
        marker in msg
        for marker in (
            "api key",
            "authentication",
            "model_decommissioned",
            "model has been decommissioned",
            "model does not exist",
            "model_not_found",
            "model_permission",
        )
    )


def score_pending_jobs() -> int:
    """Score unscored jobs, best-first, within the daily token budget."""
    resume = get_resume_text()
    if len(resume.strip()) < MIN_RESUME_CHARS:
        log.error(
            f"Resume text is missing or too short ({len(resume.strip())} chars); "
            "ATS scoring aborted so false zero scores are not written."
        )
        raise RuntimeError("ATS scoring requires a readable resume PDF.")
    _get_client()
    pending = get_unscored_jobs(limit=None)
    ready = [
        job for job in pending
        if len((job.get("description") or "").strip()) >= MIN_DESCRIPTION_CHARS
    ]
    jobs = ready[:500]
    missing_descriptions = len(pending) - len(ready)

    if missing_descriptions:
        log.warning(
            f"Skipping {missing_descriptions} unscored jobs with descriptions "
            f"shorter than {MIN_DESCRIPTION_CHARS} characters; they remain pending."
        )

    if not jobs:
        log.info("No unscored jobs with complete descriptions found.")
        return 0

    # Quality-first: highest-value jobs scored first within the budget.
    jobs.sort(key=_priority, reverse=True)
    log.info(
        f"{len(jobs)} unscored jobs. Scoring best-first within "
        f"~{GROQ_DAILY_TOKEN_BUDGET:,} tokens/day, {SCORE_DELAY_SECONDS}s apart."
    )

    used_tokens = 0
    scored = 0
    attempted = 0
    daily_limit_hit = False
    last_error: Exception | None = None
    for job in jobs:
        if used_tokens >= GROQ_DAILY_TOKEN_BUDGET:
            log.info(
                f"Daily token budget reached (~{used_tokens:,} tokens). "
                f"Scored {scored}; remaining {len(jobs) - scored} will be "
                f"scored on the next run."
            )
            break

        jd = job.get("description", "").strip()
        attempted += 1
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
                tab=job.get("_sheet_tab"),
            )
            scored += 1
            log.info(f"  {job['company']} | {job['title']} → {result['ats_score']}/100 ({result['fit_tier']})")
            time.sleep(SCORE_DELAY_SECONDS)
        except Exception as e:
            if _is_daily_limit(e):
                daily_limit_hit = True
                log.warning(
                    f"GROQ daily token limit hit. Scored {scored}; "
                    f"remaining {len(jobs) - scored} will be scored next run."
                )
                break
            if _is_fatal_api_error(e):
                raise RuntimeError(f"Groq configuration error: {e}") from e
            last_error = e
            log.warning(f"Scoring failed for {job['job_hash']}: {e}")

    if attempted and not scored and not daily_limit_hit:
        raise RuntimeError(
            f"ATS scoring failed for all {attempted} attempted jobs. "
            f"Last error: {last_error}"
        )
    log.info(f"Scoring complete: {scored} jobs scored this run.")
    return scored
