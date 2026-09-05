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
    ("Software Engineer, L5", "level"),
    ("Software Engineering Intern", "level"),
    ("Engineering Manager", "level"),
    ("Tech Lead, Platform", "level"),
    ("Leadership Development Program Engineer", None),   # 'lead' no longer a term at all
    ("Product Lead", None),                               # bare 'lead' removed by design
    ("Product Manager", None),                            # bare 'manager' removed by design
    ("Implementation Manager", None),
    ("Forward Deployed Product Manager", None),
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


@pytest.mark.parametrize("title,expected", [
    ("Associate Product Manager", None),                  # bypass beats nothing here anyway
    ("Senior Associate Product Manager", None),           # bypass skips the level check
    ("Software Engineer I", None),                        # trailing level I
    ("Software Engineer I, Platform", None),
    ("Engineer I (Remote)", None),
    ("Software Engineer II", "level"),                    # 'ii' is not 'i'
    ("A.I. Engineering Intern", "level"),                 # 'A.I.' is not level I; intern is hard
    ("Senior A.I. Engineer", "level"),
    ("Associate Software Engineering Intern", "level"),   # intern is never bypassed
    ("Staff Engineer (University Grad)", None),
    ("Junior Engineering Manager", None),
    ("Associate Counsel", "function"),                    # function still applies
    ("Associate Recruiter", "function"),
    ("Cohort 0", None),
])
def test_early_career_bypass(title, expected):
    assert prefilter(mk(title=title)) == expected


@pytest.mark.parametrize("location,remote,expected", [
    ("San Francisco", None, None),
    ("Palo Alto, CA", False, None),
    ("San Carlos, CA", False, None),
    ("Fremont, CA", False, None),
    ("New York", False, None),                            # US city: kept, model tags location_fit
    ("New York, New York, United States", False, None),
    ("Austin, TX", False, None),
    ("Boston, MA, Massachusetts", False, None),
    ("Los Angeles, California", False, None),
    ("United States", False, None),                       # bare US: kept
    ("USA (Houston)", False, None),
    ("Remote - US", True, None),
    ("Remote", True, None),
    ("Remote", None, None),
    ("N/A", None, None),
    ("", None, None),
    ("USA, Chile, UK, Uruguay, Canada", True, None),      # US-inclusive beats non-US
    ("London", False, "location"),
    ("London", True, "location"),
    ("Lisbon, Portugal", False, "location"),
    ("Guatemala", False, "location"),
    ("Remote (EMEA)", True, "location"),
    ("Remote - Canada", True, "location"),
    ("Toronto, CA", False, "location"),                   # ambiguous 'CA' loses to 'toronto'
    ("Toronto / Remote - Canada", True, "location"),
    ("Chile, Remote", True, "location"),
    ("Latin America", None, "location"),
    ("Calgary AB", False, "location"),
    ("Dublin", None, "location"),
    ("Paris", None, "location"),
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
