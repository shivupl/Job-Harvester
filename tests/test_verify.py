import json
from datetime import datetime, timedelta, timezone

import httpx

from jobwatch.http import Http
from jobwatch.store import Store
from jobwatch.verify import probe, verify

NOW = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)


def router(boards):
    """boards: {(ats, slug): job_count}"""
    def handler(req):
        host, path = req.url.host, req.url.path
        if host == "boards-api.greenhouse.io":
            slug = path.split("/")[3]
            n = boards.get(("greenhouse", slug))
            return httpx.Response(200, json={"jobs": [{"id": i, "company_name": slug.title()} for i in range(n)]}) if n is not None else httpx.Response(404)
        if host in ("api.lever.co", "api.eu.lever.co"):
            slug = path.split("/")[3]
            n = boards.get(("lever", slug))
            return httpx.Response(200, json=[{"id": str(i)} for i in range(n)]) if n is not None else httpx.Response(404)
        if host == "api.ashbyhq.com":
            slug = path.split("/")[3]
            n = boards.get(("ashby", slug))
            return httpx.Response(200, json={"jobs": [{"id": str(i), "isListed": True} for i in range(n)]}) if n is not None else httpx.Response(404)
        return httpx.Response(500)
    return handler


def make_http(handler):
    return Http(rps=1000, workers=5, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_probe_records_first_ats_with_postings():
    http = make_http(router({("greenhouse", "empty"): 0, ("ashby", "empty"): 2, ("lever", "lv"): 5}))
    assert await probe(http, "empty") == {"slug": "empty", "ats": "ashby", "name": "empty", "open_roles": 2}
    assert await probe(http, "lv") == {"slug": "lv", "ats": "lever", "name": "lv", "open_roles": 5}
    assert await probe(http, "nobody") is None


async def test_verify_writes_companies_and_caches_dead(tmp_path):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("acme\nzed\ngone\nskipme\n")
    store = Store(tmp_path / "t.db")
    store.mark_dead("skipme", NOW - timedelta(days=2))
    store.mark_dead("zed", NOW - timedelta(days=45))   # expired; must be re-probed
    http = make_http(router({("greenhouse", "acme"): 3, ("ashby", "zed"): 1, ("ashby", "skipme"): 9}))
    out = tmp_path / "companies.json"
    summary = await verify(http, seeds, out, store, dead_days=30, now=NOW)
    companies = json.loads(out.read_text())
    assert [c["slug"] for c in companies] == ["acme", "zed"]
    assert companies[0] == {"slug": "acme", "ats": "greenhouse", "name": "Acme", "open_roles": 3,
                            "verified_at": "2026-09-04T14:00:00+00:00"}
    assert summary == {"seeds": 4, "skipped_dead": 1, "resumed": 0, "probed": 3, "confirmed": 2}
    assert store.dead_slugs(30, NOW) == {"skipme", "gone"}


async def test_verify_writes_after_each_chunk(tmp_path):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("a\nb\nc\n")
    out = tmp_path / "companies.json"
    writes = []

    def handler(req):
        if out.exists():
            writes.append(len(json.loads(out.read_text())))
        return router({("ashby", "a"): 1, ("ashby", "b"): 1, ("ashby", "c"): 1})(req)

    summary = await verify(make_http(handler), seeds, out, Store(tmp_path / "t.db"), now=NOW, chunk=1)
    assert summary["confirmed"] == 3
    assert writes and max(writes) >= 1   # the file existed with content while later probes ran


async def test_verify_resumes_from_fresh_companies_file(tmp_path):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("done\nnew\nstale\n")
    out = tmp_path / "companies.json"
    out.write_text(json.dumps([
        {"slug": "done", "ats": "ashby", "name": "done", "open_roles": 1, "verified_at": (NOW - timedelta(hours=2)).isoformat()},
        {"slug": "stale", "ats": "ashby", "name": "stale", "open_roles": 1, "verified_at": (NOW - timedelta(days=7)).isoformat()},
    ]))
    probed = []

    def handler(req):
        probed.append(req.url.path.split("/")[3])
        return router({("ashby", "new"): 2, ("ashby", "stale"): 3})(req)

    summary = await verify(make_http(handler), seeds, out, Store(tmp_path / "t.db"), now=NOW)
    assert "done" not in probed and "new" in probed and "stale" in probed
    assert summary["resumed"] == 1 and summary["probed"] == 2 and summary["confirmed"] == 3
    assert [c["slug"] for c in json.loads(out.read_text())] == ["done", "new", "stale"]
