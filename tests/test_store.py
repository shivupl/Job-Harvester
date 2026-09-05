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
    s.insert(mk(2), "scored", "good fit", NOW, location="SF", url="u", score=8, level="new_grad",
             new_grad_fit=0.9, years_stated=1)
    assert not s.is_empty() and s.has("ashby:acme:1") and not s.has("ashby:acme:3")
    row = s.get("ashby:acme:2")
    assert row["score"] == 8 and row["title"] == "Job 2" and row["company"] == "Acme"
    dropped = s.get("ashby:acme:1")
    assert dropped["title"] == "Job 1" and dropped["reason"] == "level" and dropped["score"] is None
    s.update("ashby:acme:1", status="scored", score=5)
    assert s.get("ashby:acme:1")["score"] == 5
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
