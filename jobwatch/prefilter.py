"""Exclusion-only prefilter. Everything that survives goes to the model."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

from .models import Posting
from .profile import PROFILE

_YEARS = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*\d{1,2}\s*\+?\s*)?(?:years?|yrs?)\b", re.I)
_EXPERIENCE = re.compile(r"experience|yoe", re.I)
_WINDOW = 40


def _terms_re(terms: list[str]) -> re.Pattern:
    alts = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    return re.compile(rf"(?<![a-z0-9])(?:{alts})(?![a-z0-9])", re.I)


def min_years(text: str) -> Optional[int]:
    """Smallest number of years that appears within 40 chars of 'experience' or 'yoe'."""
    best: Optional[int] = None
    for m in _YEARS.finditer(text):
        window = text[max(0, m.start() - _WINDOW): m.end() + _WINDOW]
        if _EXPERIENCE.search(window):
            n = int(m.group(1))
            best = n if best is None else min(best, n)
    return best


def is_stale(posted_at: Optional[str], now: datetime, max_days: int) -> bool:
    if not posted_at:
        return False
    try:
        dt = datetime.fromisoformat(posted_at)
    except ValueError:
        return False
    return dt < now - timedelta(days=max_days)


def _location_ok(p: Posting, profile: dict) -> bool:
    """Keep anything that could be Bay Area, US-remote, or US anywhere.

    A US signal beats a non-US term (multi-region remote that includes the US
    is kept). Two-letter state codes are ambiguous ("Toronto, CA"), so they only
    count when no non-US term is present. Location no longer affects the score;
    the model tags location_fit and the digest shows it.
    """
    low = p.location.strip().lower()
    if low in ("", "n/a"):
        return True
    if _terms_re(profile["bay_area_terms"]).search(low):
        return True
    non_us = _terms_re(profile["non_us_terms"]).search(low) is not None
    if _terms_re(profile["us_terms"]).search(low):
        return True
    states = profile["us_states"]
    if _terms_re([t for t in states if len(t) > 2]).search(low):
        return True
    if not non_us and _terms_re([t for t in states if len(t) == 2]).search(low):
        return True
    if p.remote is True and not non_us:
        return True
    if "remote" in low and not non_us:      # text wins regardless of the ATS flag
        return True
    return False


# "Staff Engineer" is senior; "Member of Technical Staff" is any level.
_STAFF = re.compile(r"(?<!technical )(?<!of )(?<![a-z0-9])staff(?![a-z0-9])", re.I)

# "Software Engineer I" / "Engineer I, Platform" / "Engineer I (Remote)" but not "A.I."
_LEVEL_ONE = re.compile(r"(?<=\s)I(?=\s*(?:$|[,(\-\u2013/|]))")


def _early_career(title: str, profile: dict) -> bool:
    return (_terms_re(profile["early_career_bypass"]).search(title) is not None
            or _LEVEL_ONE.search(title) is not None)


def prefilter(p: Posting, profile: dict = PROFILE) -> Optional[str]:
    if _terms_re(profile["hard_level_terms"]).search(p.title):
        return "level"
    if not _early_career(p.title, profile):
        if _terms_re(profile["level_terms"]).search(p.title) or _STAFF.search(p.title):
            return "level"
    if not _terms_re(profile["builder_bypass"]).search(p.title):
        if _terms_re(profile["function_terms"]).search(p.title):
            return "function"
    if not _location_ok(p, profile):
        return "location"
    if profile.get("max_years") is not None:
        years = min_years(p.title + "\n" + p.description)
        if years is not None and years > profile["max_years"]:
            return "years"
    return None
