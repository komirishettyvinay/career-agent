from groq import Groq
from config.settings import GROQ_API_KEY, GROQ_MODEL
from src.analyzer.resume_parser import get_resume_text

_client: Groq | None = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")
        _client = Groq(api_key=GROQ_API_KEY)
    return _client

SYSTEM_PROMPT = """You are helping Vinay Komirishetty, a Data Engineer with 5 years of experience,
answer job application screening questions.

Rules:
- Answer ONLY using experience that exists in the resume provided. Never fabricate.
- Be specific: name technologies, companies, and metrics from the resume.
- Keep answers concise: 2-4 sentences unless the question clearly needs more.
- Write in first person as Vinay.
- If the resume doesn't contain relevant experience for the question, say so honestly
  and pivot to the closest transferable skill."""

USER_TEMPLATE = """MY RESUME:
{resume}

JOB CONTEXT (if provided):
{job_context}

APPLICATION QUESTION:
{question}"""


def answer(question: str, job_context: str = "", resume_text: str = "") -> str:
    resume = resume_text or get_resume_text()
    resp = _get_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_TEMPLATE.format(
                    resume=resume,
                    job_context=job_context or "Not provided",
                    question=question,
                ),
            },
        ],
        temperature=0.3,
        max_tokens=600,
    )
    return resp.choices[0].message.content.strip()
