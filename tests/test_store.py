from datetime import datetime, timedelta, timezone

from jobwatch.models import Posting
from jobwatch.store import Store

NOW = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)


def mk(i, **kw):
    d = dict(ats="ashby", slug="acme", job_id=str(i), title=f"Job {i}", company="Acme",
             location="SF", remote=None, description="", posted_at="2026-09-01T00:00:00+00:00", url="u")
    d.update(kw)
    return Posting(**d)


def test_insert_has_update_and_audit(tmp_path):
    s = Store(tmp_path / "t.db")
    assert s.is_empty()
    s.insert(mk(1), "dropped", "level", NOW)
    s.insert(mk(2), "scored", "good fit", NOW, location="SF", url="u", fit=8, relevance=9, level="new_grad",
             category="fde", location_fit="bay_area", years_stated=1)
    assert not s.is_empty() and s.has("ashby:acme:1") and not s.has("ashby:acme:3")
    row = s.get("ashby:acme:2")
    assert row["fit"] == 8 and row["relevance"] == 9 and row["category"] == "fde" and row["title"] == "Job 2"
    dropped = s.get("ashby:acme:1")
    assert dropped["title"] == "Job 1" and dropped["reason"] == "level" and dropped["fit"] is None
    s.update("ashby:acme:1", status="scored", fit=5)
    assert s.get("ashby:acme:1")["fit"] == 5
    s.insert(mk(3), "dropped", "level", NOW)
    s.insert(mk(4), "dropped", "years", NOW)
    assert s.audit() == [("level", 1), ("years", 1)]   # ordered by count desc, then reason


def test_dead_slugs_expire(tmp_path):
    s = Store(tmp_path / "t.db")
    s.mark_dead("old", NOW - timedelta(days=40))
    s.mark_dead("fresh", NOW - timedelta(days=5))
    assert s.dead_slugs(30, NOW) == {"fresh"}
    s.unmark_dead("fresh")
    assert s.dead_slugs(30, NOW) == set()


def test_prune_and_monthly_vacuum(tmp_path):
    s = Store(tmp_path / "t.db")
    s.insert(mk(1), "baseline", None, NOW - timedelta(days=100))
    s.insert(mk(2), "baseline", None, NOW - timedelta(days=10))
    assert s.prune(90, NOW) == 1
    assert not s.has("ashby:acme:1") and s.has("ashby:acme:2")
    assert s.maybe_vacuum(NOW) is True
    assert s.maybe_vacuum(NOW + timedelta(days=3)) is False
    assert s.maybe_vacuum(NOW + timedelta(days=40)) is True


def test_record_run(tmp_path):
    s = Store(tmp_path / "t.db")
    s.record_run(NOW, "morning", fetched=10, new=3, stale=1, prefiltered=1, scored=1, shown=1)
    assert tuple(s.con.execute("select slot, fetched, shown from runs").fetchone()) == ("morning", 10, 1)


def test_migration_adds_columns_to_old_db(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    con = sqlite3.connect(str(path))
    con.execute("create table seen (key text primary key, first_seen text not null, posted_at text, title text, "
                "company text, status text not null, reason text, location text, url text, score integer, "
                "level text, new_grad_fit real, years_stated integer)")
    con.execute("insert into seen(key, first_seen, status) values ('a:b:1', '2026-09-01T00:00:00+00:00', 'baseline')")
    con.commit(); con.close()
    s = Store(path)
    cols = {r[1] for r in s.con.execute("pragma table_info(seen)")}
    assert {"fit", "relevance", "category", "location_fit"} <= cols
    assert s.has("a:b:1")


def test_release_baseline_since_also_releases_level_and_location_drops(tmp_path):
    s = Store(tmp_path / "t.db")
    s.insert(mk(1, posted_at="2026-09-03T00:00:00+00:00"), "baseline", None, NOW)
    s.insert(mk(2, posted_at="2026-09-03T00:00:00+00:00"), "dropped", "level", NOW)
    s.insert(mk(3, posted_at="2026-09-03T00:00:00+00:00"), "dropped", "location", NOW)
    s.insert(mk(4, posted_at="2026-09-03T00:00:00+00:00"), "dropped", "function", NOW)
    s.insert(mk(5, posted_at="2026-09-03T00:00:00+00:00"), "scored", "x", NOW, fit=7, relevance=7)
    s.insert(mk(6, posted_at="2026-08-01T00:00:00+00:00"), "baseline", None, NOW)
    s.insert(mk(7, posted_at="2026-09-03T00:00:00+00:00"), "scored", "legacy", NOW, score=8)   # no fit: legacy
    assert s.release_baseline_since("2026-09-01T00:00:00+00:00") == 4
    assert not s.has("ashby:acme:1") and not s.has("ashby:acme:2") and not s.has("ashby:acme:3")
    assert not s.has("ashby:acme:7")
    assert s.has("ashby:acme:4") and s.has("ashby:acme:5") and s.has("ashby:acme:6")


def test_release_with_rescore_also_releases_scored_and_unscored(tmp_path):
    s = Store(tmp_path / "t.db")
    s.insert(mk(1, posted_at="2026-09-03T00:00:00+00:00"), "scored", "x", NOW, fit=9, relevance=9)
    s.insert(mk(2, posted_at="2026-09-03T00:00:00+00:00"), "unscored", None, NOW)
    s.insert(mk(3, posted_at="2026-09-03T00:00:00+00:00"), "dropped", "function", NOW)
    s.insert(mk(4, posted_at="2026-08-01T00:00:00+00:00"), "scored", "x", NOW, fit=9, relevance=9)
    s.insert(mk(5, posted_at="2026-09-03T00:00:00+00:00"), "stale", "stale", NOW)
    assert s.release_baseline_since("2026-09-01T00:00:00+00:00", rescore=True) == 3
    assert not s.has("ashby:acme:1") and not s.has("ashby:acme:2") and not s.has("ashby:acme:3")
    assert s.has("ashby:acme:4") and s.has("ashby:acme:5")   # outside window; stale untouched
