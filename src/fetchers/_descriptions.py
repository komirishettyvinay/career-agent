"""Helpers for extracting useful plain-text job descriptions."""

import html
import json
import re
from html.parser import HTMLParser

import requests


class _TextExtractor(HTMLParser):
    _BREAK_TAGS = {
        "br", "p", "div", "li", "ul", "ol", "section", "article",
        "h1", "h2", "h3", "h4", "h5", "h6", "tr",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() in self._BREAK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str):
        if tag.lower() in self._BREAK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str):
        self.parts.append(data)


def html_to_text(value: str) -> str:
    """Convert HTML-ish content to compact readable text."""
    if not value:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(html.unescape(str(value)))
        raw = "".join(parser.parts)
    except Exception:
        raw = re.sub(r"<[^>]+>", " ", str(value))
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def lever_description(posting: dict) -> str:
    """Build a description from the fields exposed by Lever's Postings API."""
    parts = [
        posting.get("openingPlain") or posting.get("opening") or "",
        posting.get("descriptionPlain") or posting.get("description") or "",
    ]
    for section in posting.get("lists") or []:
        parts.append(section.get("text", ""))
        parts.append(section.get("content", ""))
    parts.append(posting.get("additionalPlain") or posting.get("additional") or "")
    return html_to_text("\n".join(str(part) for part in parts if part))


def _find_job_posting(value):
    if isinstance(value, dict):
        item_type = value.get("@type")
        if item_type == "JobPosting" or (
            isinstance(item_type, list) and "JobPosting" in item_type
        ):
            return value
        for child in value.values():
            found = _find_job_posting(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_job_posting(child)
            if found:
                return found
    return None


def description_from_page(page_html: str) -> str:
    """Extract a JobPosting description from public page metadata."""
    if not page_html:
        return ""
    scripts = re.findall(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for script in scripts:
        try:
            posting = _find_job_posting(json.loads(html.unescape(script.strip())))
        except (json.JSONDecodeError, TypeError):
            continue
        if posting and posting.get("description"):
            return html_to_text(posting["description"])
    return ""


def fetch_page_description(url: str, session=None, timeout: int = 10) -> str:
    """Fetch a public apply page and extract its structured job description."""
    if not url:
        return ""
    client = session or requests.Session()
    try:
        response = client.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 JobHunterBot/1.0"},
        )
        if response.status_code != 200:
            return ""
        return description_from_page(response.text)
    except requests.RequestException:
        return ""
