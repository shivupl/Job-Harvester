from datetime import datetime, timezone

import pytest

from jobwatch.models import Posting
from jobwatch.prefilter import is_stale, min_years, prefilter

NOW = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)


def mk(title="Software Engineer", location="San Francisco", remote=None, description="", ats="ashby"):
    return Posting(ats=ats, slug="s", job_id="1", title=title, company="C", location=location,
                   remote=remote, description=description, posted_at=None, url="u")


@pytest.mark.parametrize("title,expected", [
    ("Senior Software Engineer", "level"),
    ("Sr. Engineer", "level"),
    ("Software Engineer II", "level"),
    ("Product Lead", "level"),
    ("Engineering Manager", "level"),
    ("Software Engineer, L5", "level"),
    ("Software Engineering Intern", "level"),
    ("Leadership Development Program Engineer", None),   # 'lead' must be word-bounded
    ("Sales Engineer", None),
    ("Solutions Engineer", None),
    ("Account Executive", "function"),
    ("Technical Recruiter", "function"),
    ("Product Designer", "function"),
    ("People Operations Partner", "function"),
    ("Forward Deployed Engineer", None),
    ("Founding Engineer", None),
    ("Software Engineer, New Grad", None),
])
def test_title_filters(title, expected):
    assert prefilter(mk(title=title)) == expected


@pytest.mark.parametrize("location,remote,expected", [
    ("San Francisco", None, None),
    ("Palo Alto, CA", False, None),
    ("New York", False, "location"),
    ("Los Angeles, California", False, "location"),
    ("London", True, "location"),
    ("Remote - US", True, None),
    ("Remote", True, None),
    ("Remote (EMEA)", True, "location"),
    ("Remote", None, None),
    ("N/A", None, None),
    ("", None, None),
    ("Dublin", None, "location"),
    ("Toronto / Remote - Canada", True, "location"),
])
def test_location_filter(location, remote, expected):
    assert prefilter(mk(location=location, remote=remote)) == expected


@pytest.mark.parametrize("text,expected", [
    ("5+ years of experience with Python", 5),
    ("3-5 years experience", 3),
    ("1–3 years of relevant experience", 1),
    ("at least 2 yrs experience", 2),
    ("Experience: 7+ years", 7),
    ("We have 10 years of runway", None),
    ("0-2 years of experience preferred", 0),
    ("", None),
])
def test_min_years(text, expected):
    assert min_years(text) == expected


def test_years_filter_reads_description_and_keeps_unknown():
    assert prefilter(mk(description="Requirements: 5+ years of experience")) == "years"
    assert prefilter(mk(description="1-3 years of experience")) is None
    assert prefilter(mk(description="no numbers here")) is None
    assert prefilter(mk(description="3 years experience")) is None


def test_first_failure_wins():
    assert prefilter(mk(title="Senior Recruiter", location="London")) == "level"


def test_is_stale():
    assert is_stale("2026-08-01T00:00:00+00:00", NOW, 14) is True
    assert is_stale("2026-09-01T00:00:00+00:00", NOW, 14) is False
    assert is_stale(None, NOW, 14) is False
