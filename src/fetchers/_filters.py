"""Shared location + role filters for all ATS fetchers."""

from config.settings import CANADA_HINTS, EXCLUDE_LOCATIONS, DATA_ROLE_KEYWORDS

_CANADA = {h.lower() for h in CANADA_HINTS}
_EXCLUDE = {e.lower() for e in EXCLUDE_LOCATIONS}
_ROLE_KW = [k.lower() for k in DATA_ROLE_KEYWORDS]

# Bare-remote phrases that carry no country → give benefit of the doubt.
_PURE_REMOTE = {"remote", "anywhere", "worldwide", "global",
                "remote - global", "fully remote", "remote, global"}


def is_data_role(title: str) -> bool:
    t = (title or "").lower()
    return any(kw in t for kw in _ROLE_KW)


def is_canadian(location: str) -> bool:
    """
    Keep a job if its location names Canada (city/province/country).
    Bare 'remote' with no country is kept. Anything that names another
    country/region is dropped — even if it also says 'remote'.
    """
    if not location:
        return True
    loc = location.lower()

    # 1. Explicit Canadian signal always wins (handles "Vancouver; Remote - US")
    if any(h in loc for h in _CANADA):
        return True

    # 2. Names an excluded country/region → drop
    if any(ex in loc for ex in _EXCLUDE):
        return False

    # 3. Bare remote with no country qualifier → keep
    if loc.strip() in _PURE_REMOTE:
        return True

    # 4. Mentions some other place we don't recognise → drop
    return False
