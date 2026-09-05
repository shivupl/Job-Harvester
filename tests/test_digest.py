from datetime import datetime, timezone

from jobwatch.digest import hours_ago, render

NOW = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)


def test_hours_ago():
    assert hours_ago("2026-09-04T08:00:00+00:00", NOW) == "6h ago"
    assert hours_ago("2026-09-01T08:00:00+00:00", NOW) == "3d ago"
    assert hours_ago(None, NOW) == ""


def test_render_groups_by_category_and_tags_location():
    funnel = {"fetched": 1420, "new": 212, "stale": 38, "prefiltered": 141, "scored": 33, "shown": 3}
    shown = [
        {"relevance": 9, "fit": 9, "category": "fde", "location_fit": "bay_area", "title": "Forward Deployed Engineer",
         "url": "https://x/1", "company": "Acme", "location": "San Francisco",
         "posted_at": "2026-09-04T08:00:00+00:00", "comp": "$150K – $190K", "reason": "Explicit 0-2 years, on-site SF."},
        {"relevance": 8, "fit": 5, "category": "swe", "location_fit": "other_us", "title": "Software Engineer",
         "url": "https://x/2", "company": "Beta", "location": "Austin, TX", "posted_at": None, "comp": None, "reason": "r2"},
        {"relevance": 7, "fit": 7, "category": "product", "location_fit": "us_remote", "title": "APM",
         "url": "https://x/3", "company": "Gamma", "location": "Remote - US", "posted_at": None, "comp": None, "reason": "r3"},
    ]
    unscored = [{"title": "Odd One", "url": "https://x/4", "company": "Delta"}]
    errors = ["lever:oldco — 404 both hosts"]
    out = render("2026-09-04", "morning", funnel, shown, unscored, errors, now=NOW)
    assert out.startswith("# jobwatch 2026-09-04 morning\n")
    assert "fetched 1420 · new 212 · stale 38 · prefiltered 141 · scored 33 · shown 3" in out
    # category order: fde, product, swe
    assert out.index("## FDE & Solutions (1)") < out.index("## Product & Strategy (1)") < out.index("## Software Engineering (1)")
    assert "- **rel 9 · fit 9** [Forward Deployed Engineer](https://x/1) — Acme · [Bay Area] · San Francisco · 6h ago · $150K – $190K" in out
    assert "  Explicit 0-2 years, on-site SF." in out
    assert "- **rel 8 · fit 5** [Software Engineer](https://x/2) — Beta · [Austin, TX] · stretch" in out
    assert "- **rel 7 · fit 7** [APM](https://x/3) — Gamma · [US remote] · Remote - US" in out
    assert "## Unscored (1)\n- [Odd One](https://x/4) — Delta" in out
    assert "## Fetch errors (1)\n- lever:oldco — 404 both hosts" in out


def test_render_empty_has_no_sections():
    out = render("2026-09-04", "midday", {"fetched": 1, "new": 0, "stale": 0, "prefiltered": 0, "scored": 0, "shown": 0}, [], [], [], now=NOW)
    assert "Unscored" not in out and "Fetch errors" not in out and "##" not in out
    assert "No new postings worth showing." in out
