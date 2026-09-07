import json
from datetime import datetime, timedelta, timezone

from jobwatch.board import render_board
from jobwatch.models import Posting
from jobwatch.profile import PROFILE
from jobwatch.store import Store

NOW = datetime(2026, 9, 5, 14, 0, tzinfo=timezone.utc)


def mk(i, title="Engineer", **kw):
    d = dict(ats="ashby", slug="acme", job_id=str(i), title=title, company="Acme", location="SF",
             remote=None, description="", posted_at=(NOW - timedelta(days=1)).isoformat(), url=f"https://x/{i}")
    d.update(kw)
    return Posting(**d)


def scored(s, i, fit, rel, loc_fit="bay_area", first_seen=NOW, cat="swe", **kw):
    s.insert(mk(i, **kw), "scored", "why", first_seen, location="SF", url=f"https://x/{i}", fit=fit,
             relevance=rel, category=cat, location_fit=loc_fit, level="new_grad")


def test_board_rows_apply_thresholds_hidden_fits_and_window(tmp_path):
    s = Store(tmp_path / "t.db")
    scored(s, 1, 9, 9)                                   # in
    scored(s, 2, 3, 9)                                   # fit below min_fit
    scored(s, 3, 9, 5)                                   # relevance below min
    scored(s, 4, 9, 9, loc_fit="non_us")                 # hidden
    scored(s, 5, 9, 9, first_seen=NOW - timedelta(days=40))   # outside window
    s.insert(mk(6), "dropped", "level", NOW)             # not scored
    rows = s.board_rows(PROFILE, NOW)
    assert [r["key"] for r in rows] == ["ashby:acme:1"]
    r = rows[0]
    assert r["title"] == "Engineer" and r["fit"] == 9 and r["relevance"] == 9 and r["category"] == "swe"
    assert r["url"] == "https://x/1" and r["reason"] == "why" and r["location_fit"] == "bay_area"


def test_board_rows_sorted_relevance_fit_newest(tmp_path):
    s = Store(tmp_path / "t.db")
    scored(s, 1, 9, 7)
    scored(s, 2, 6, 9, posted_at=(NOW - timedelta(days=3)).isoformat())
    scored(s, 3, 8, 9, posted_at=(NOW - timedelta(days=2)).isoformat())
    scored(s, 4, 8, 9, posted_at=(NOW - timedelta(hours=1)).isoformat())
    assert [r["key"][-1] for r in s.board_rows(PROFILE, NOW)] == ["4", "3", "2", "1"]


def test_render_board_embeds_rows_and_escapes():
    rows = [{"key": "ashby:acme:1", "title": "<b>Evil</b> & Co", "company": "Acme", "url": "https://x/1",
             "fit": 9, "relevance": 8, "category": "fde", "location_fit": "bay_area", "location": "SF",
             "posted_at": "2026-09-04T14:00:00+00:00", "comp": "$100K", "reason": "a <reason>",
             "first_seen": "2026-09-05T14:00:00+00:00"}]
    html = render_board(rows, NOW, PROFILE)
    assert html.startswith("<!doctype html>")
    assert "<b>Evil</b>" not in html                       # no raw HTML from data
    data = json.loads(html.split('id="data" type="application/json">')[1].split("</script>")[0])
    assert data["rows"][0]["title"] == "<b>Evil</b> & Co" and data["rows"][0]["key"] == "ashby:acme:1"
    assert data["generated_at"].startswith("2026-09-05")
    assert "localStorage" in html and "stretch_fit" in html
    assert "</script>" not in json.dumps(data)              # the JSON block can't terminate itself early


def test_render_board_escapes_script_terminator_in_data():
    rows = [{"key": "k", "title": "x</script><script>alert(1)</script>", "company": "", "url": "", "fit": 9,
             "relevance": 9, "category": "swe", "location_fit": "unknown", "location": "", "posted_at": None,
             "comp": None, "reason": "", "first_seen": "2026-09-05T14:00:00+00:00"}]
    html = render_board(rows, NOW, PROFILE)
    block = html.split('id="data" type="application/json">')[1].split("</script>")[0]
    assert "alert(1)" in block and "</script>" not in block


def test_new_grad_cards_are_marked_and_seen_button_is_gone(tmp_path):
    s = Store(tmp_path / "t.db")
    scored(s, 1, 9, 9)
    html = render_board(s.board_rows(PROFILE, NOW), NOW, PROFILE)
    assert "card.newgrad" in html and "--gold:" in html          # style present in the CSS
    assert "data-seen" not in html and "seenbtn" not in html     # no corner button on cards
    assert "r.level === 'new_grad'" in html                       # class is driven by the scorer's level
    assert 'data-act="applied"' in html and 'data-act="hidden"' in html
    assert "jobwatch.applied" in html and "jobwatch.hidden" in html   # persisted per browser
    assert 'id="view"' in html and 'id="hideseen"' not in html
