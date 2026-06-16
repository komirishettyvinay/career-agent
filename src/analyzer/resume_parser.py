import fitz  # pymupdf
from config.settings import RESUME_PATH

_cached_text: str | None = None


def parse_from_bytes(pdf_bytes: bytes) -> str:
    """Parse PDF from raw bytes — used on Streamlit Cloud where user uploads resume."""
    global _cached_text
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    _cached_text = text
    return text


def get_resume_text() -> str:
    global _cached_text
    if _cached_text:
        return _cached_text
    try:
        doc = fitz.open(RESUME_PATH)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        _cached_text = text
        return text
    except Exception:
        return ""
