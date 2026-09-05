import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx

from jobwatch.http import Http
from jobwatch.models import Posting
from jobwatch.profile import PROFILE
from jobwatch.run import run
from jobwatch.store import Store

NOW = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)   # 07:00 PDT


def ashby_job(i, title, published, location="San Francisco", desc="New grads welcome."):
    return {"id": f"j{i}", "title": title, "isListed": True, "isRemote": False, "workplaceType": "OnSite",
            "location": location, "secondaryLocations": [], "publishedAt": published,
            "jobUrl": f"https://jobs.ashbyhq.com/acme/j{i}", "descriptionPlain": desc, "compensation": None}


class FakeClient:
    def __init__(self, score=8):
        self.score = score
        self.calls = 0
        self.messages = self

    async def create(self, **kw):
        self.calls += 1
        text = json.dumps({"level": "new_grad", "new_grad_fit": 0.8, "years_stated": -1,
                           "score": self.score, "reason": "fits"})
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def make_http(jobs):
    def handler(req):
        if req.url.host == "api.ashbyhq.com" and req.url.path.endswith("/acme"):
            return httpx.Response(200, json={"jobs": jobs})
        return httpx.Response(404)
    return Http(rps=1000, workers=5, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def setup(tmp_path):
    companies = tmp_path / "companies.json"
    companies.write_text(json.dumps([
        {"slug": "acme", "ats": "ashby", "name": "acme", "open_roles": 1, "verified_at": "x"},
        {"slug": "gone", "ats": "greenhouse", "name": "gone", "open_roles": 1, "verified_at": "x"},
    ]))
    return companies, Store(tmp_path / "t.db"), tmp_path / "digests"


async def test_baseline_then_diff_then_digest(tmp_path):
    companies, store, digests = setup(tmp_path)
    fresh = (NOW - timedelta(hours=6)).isoformat()
    old = (NOW - timedelta(days=30)).isoformat()
    jobs = [ashby_job(1, "Forward Deployed Engineer", fresh), ashby_job(2, "Senior Engineer", fresh)]
    client = FakeClient()

    r1 = await run(make_http(jobs), store, client, companies, digests, "morning", PROFILE, now=NOW)
    assert r1.baseline and r1.digest_path is None and client.calls == 0
    assert store.get("ashby:acme:j1")["status"] == "baseline"

    jobs2 = jobs + [
        ashby_job(3, "Founding Engineer", fresh),
        ashby_job(4, "Staff Engineer", fresh),
        ashby_job(5, "Software Engineer", old),
        ashby_job(6, "Solutions Engineer", fresh, location="London"),
    ]
    later = NOW + timedelta(hours=5)
    r2 = await run(make_http(jobs2), store, client, companies, digests, "midday", PROFILE, now=later)
    assert not r2.baseline and r2.shown == 1 and client.calls == 1
    assert r2.funnel == {"fetched": 6, "new": 4, "stale": 1, "prefiltered": 2, "scored": 1, "shown": 1}
    assert store.get("ashby:acme:j3")["score"] == 8
    assert store.get("ashby:acme:j4")["reason"] == "level" and store.get("ashby:acme:j4")["title"] == "Staff Engineer"
    assert store.get("ashby:acme:j5")["status"] == "stale"
    assert store.get("ashby:acme:j6")["reason"] == "location"
    assert r2.digest_path == digests / "2026-09-04-midday.md"
    text = r2.digest_path.read_text()
    assert "[Founding Engineer](https://jobs.ashbyhq.com/acme/j3)" in text
    assert "## Fetch errors (1)" in text and "greenhouse:gone" in text

    r3 = await run(make_http(jobs2), store, client, companies, digests, "evening", PROFILE, now=later + timedelta(hours=5))
    assert r3.shown == 0 and r3.funnel["new"] == 0 and client.calls == 1
    assert (digests / "2026-09-04-evening.md").exists()


async def test_low_score_not_shown_and_unscored_surfaced(tmp_path):
    companies, store, digests = setup(tmp_path)
    fresh = (NOW - timedelta(hours=1)).isoformat()
    await run(make_http([]), store, FakeClient(), companies, digests, "morning", PROFILE, now=NOW)
    store.insert(  # make the store non-empty so the next run is not a baseline
        Posting(ats="ashby", slug="acme", job_id="seed", title="x", company="acme", location="",
                remote=None, description="", posted_at=None, url=""), "baseline", None, NOW)

    class Bad(FakeClient):
        async def create(self, **kw):
            self.calls += 1
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="nope")])

    jobs = [ashby_job(1, "Product Engineer", fresh)]
    r = await run(make_http(jobs), store, Bad(), companies, digests, "midday", PROFILE, now=NOW)
    assert r.shown == 0 and store.get("ashby:acme:j1")["status"] == "unscored"
    assert "## Unscored (1)" in r.digest_path.read_text()

    r = await run(make_http(jobs + [ashby_job(2, "Product Engineer", fresh)]), store, FakeClient(score=4),
                  companies, digests, "evening", PROFILE, now=NOW)
    assert r.shown == 0 and store.get("ashby:acme:j2")["score"] == 4
