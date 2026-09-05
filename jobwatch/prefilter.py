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
    low = p.location.strip().lower()
    if low in ("", "n/a"):
        return True
    if _terms_re(profile["bay_area_terms"]).search(low):
        return True
    non_us = _terms_re(profile["non_us_terms"]).search(low) is not None
    if p.remote is True and not non_us:
        return True
    if p.remote is None and "remote" in low and not non_us:
        return True
    return False


def prefilter(p: Posting, profile: dict = PROFILE) -> Optional[str]:
    if _terms_re(profile["level_terms"]).search(p.title):
        return "level"
    if _terms_re(profile["function_terms"]).search(p.title):
        return "function"
    if not _location_ok(p, profile):
        return "location"
    years = min_years(p.title + "\n" + p.description)
    if years is not None and years > profile["max_years"]:
        return "years"
    return None
