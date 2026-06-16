import json
import logging
from groq import Groq
from config.settings import GROQ_API_KEY, GROQ_MODEL, TIER_STRONG, TIER_MAYBE
from src.analyzer.resume_parser import get_resume_text
from src.storage.database import get_unscored_jobs, update_ats

log = logging.getLogger(__name__)
_client: Groq | None = None


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


def _score_one(resume: str, jd: str) -> dict:
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
    return json.loads(raw)


def score_pending_jobs():
    """Score all jobs that haven't been scored yet."""
    resume = get_resume_text()
    jobs   = get_unscored_jobs(limit=100)

    if not jobs:
        log.info("No unscored jobs found.")
        return

    log.info(f"Scoring {len(jobs)} jobs with GROQ...")

    for job in jobs:
        jd = job.get("description", "")
        if not jd:
            continue
        try:
            result = _score_one(resume, jd)
            update_ats(
                job_hash=job["job_hash"],
                score=result["ats_score"],
                matched=json.dumps(result.get("matched_keywords", [])),
                missing=json.dumps(result.get("missing_keywords", [])),
                tier=result["fit_tier"],
                summary=result["summary"],
                skills=json.dumps(result.get("skills_required", [])),
            )
            log.info(f"  {job['company']} | {job['title']} → {result['ats_score']}/100 ({result['fit_tier']})")
        except Exception as e:
            log.warning(f"Scoring failed for {job['job_hash']}: {e}")
