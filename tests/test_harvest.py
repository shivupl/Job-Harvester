from pathlib import Path

import httpx

from jobwatch.harvest import (
    extract_short_codes, extract_slugs, harvest, is_valid_slug, list_threads,
    merge_seeds, resolve_short,
)
from jobwatch.http import Http


def test_extract_slugs_from_escaped_algolia_json(fixture_text):
    raw = fixture_text("hn_thread.json")
    assert extract_slugs(raw) == {
        "oklo", "smarkets", "findigs", "euco", "embedco", "eggai", "Nested.Co",
    }


def test_extract_without_unescape_finds_nothing(fixture_text):
    import re
    raw = fixture_text("hn_thread.json")
    assert not re.findall(r"job-boards\.greenhouse\.io/([A-Za-z0-9_-]+)", raw)


def test_blocklist_and_extensions():
    assert not is_valid_slug("embed")
    assert not is_valid_slug("static")
    assert not is_valid_slug("logo.png")
    assert not is_valid_slug("Embed")
    assert is_valid_slug("arch.co")
    assert is_valid_slug("Nested.Co")
    assert is_valid_slug("oklo")


def test_extract_short_codes(fixture_text):
    assert extract_short_codes(fixture_text("hn_thread.json")) == {"0572f98b4us"}


def make_http(handler):
    return Http(rps=1000, workers=5, client=httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False))


async def test_resolve_short_head_then_get_fallback():
    seen = []

    def handler(req):
        seen.append(req.method)
        if req.method == "HEAD":
            return httpx.Response(405)
        return httpx.Response(301, headers={
            "Location": "https://job-boards.greenhouse.io/sourcegraph91?gh_src=0572f98b4us"})

    assert await resolve_short(make_http(handler), "0572f98b4us") == "sourcegraph91"
    assert seen == ["HEAD", "GET"]


async def test_resolve_short_company_site_yields_nothing():
    def handler(req):
        return httpx.Response(301, headers={
            "Location": "https://www.chronograph.pe/jobs/?gh_jid=5187048007&gh_src=x"})

    assert await resolve_short(make_http(handler), "abc") is None


async def test_resolve_short_eu_host_and_job_path():
    def handler(req):
        return httpx.Response(301, headers={
            "Location": "https://boards.greenhouse.io/justworks/jobs/7957539?gh_jid=7957539"})

    assert await resolve_short(make_http(handler), "abc") == "justworks"


async def test_list_threads_filters_and_limits(fixture_json):
    def handler(req):
        page = int(req.url.params.get("page", "0"))
        if page == 0:
            data = fixture_json("hn_search.json")
            data["hits"].append({"objectID": "1", "title": "Ask HN: Who wants to be hired? (September 2026)",
                                 "created_at": "2026-09-01T15:02:00Z"})
            data["nbPages"] = 1
            return httpx.Response(200, json=data)
        return httpx.Response(200, json={"hits": [], "nbPages": 1})

    threads = await list_threads(make_http(handler), months=None)
    assert [t["objectID"] for t in threads] == ["49522897", "49156683"]
    assert [t["objectID"] for t in await list_threads(make_http(handler), months=1)] == ["49522897"]


def test_merge_seeds_dedupes_case_sensitively(tmp_path: Path):
    p = tmp_path / "seeds.txt"
    p.write_text("acme\nZeta\n")
    merged, new = merge_seeds(p, {"acme", "beta", "Zeta", "zeta"})
    assert merged == ["Zeta", "acme", "beta", "zeta"]
    assert new == 2
    assert p.read_text() == "Zeta\nacme\nbeta\nzeta\n"


async def test_harvest_end_to_end(fixture_json, fixture_text, tmp_path: Path):
    def handler(req):
        if "search_by_date" in req.url.path:
            page = int(req.url.params.get("page", "0"))
            if page == 0:
                d = fixture_json("hn_search.json"); d["nbPages"] = 1
                return httpx.Response(200, json=d)
            return httpx.Response(200, json={"hits": [], "nbPages": 1})
        if req.url.path.startswith("/api/v1/items/"):
            return httpx.Response(200, text=fixture_text("hn_thread.json"))
        if req.url.host == "grnh.se":
            return httpx.Response(301, headers={"Location": "https://job-boards.greenhouse.io/sourcegraph91"})
        return httpx.Response(404)

    seeds = tmp_path / "seeds.txt"
    summary = await harvest(make_http(handler), seeds, months=None)
    got = set(seeds.read_text().split())
    assert "sourcegraph91" in got and "oklo" in got and "Nested.Co" in got
    assert summary["threads"] == 2 and summary["short_codes"] == 1


async def test_harvest_caches_short_link_resolution(fixture_json, fixture_text, tmp_path: Path):
    from jobwatch.store import Store
    heads = []

    def handler(req):
        if "search_by_date" in req.url.path:
            page = int(req.url.params.get("page", "0"))
            if page == 0:
                d = fixture_json("hn_search.json"); d["nbPages"] = 1
                return httpx.Response(200, json=d)
            return httpx.Response(200, json={"hits": [], "nbPages": 1})
        if req.url.path.startswith("/api/v1/items/"):
            return httpx.Response(200, text=fixture_text("hn_thread.json"))
        if req.url.host == "grnh.se":
            heads.append(req.url.path)
            return httpx.Response(301, headers={"Location": "https://job-boards.greenhouse.io/sourcegraph91"})
        return httpx.Response(404)

    seeds = tmp_path / "seeds.txt"
    store = Store(tmp_path / "t.db")
    s1 = await harvest(make_http(handler), seeds, months=None, store=store)
    assert len(heads) == 1 and s1["short_codes"] == 1 and s1["resolved"] == 1
    s2 = await harvest(make_http(handler), seeds, months=None, store=store)
    assert len(heads) == 1                                  # cached: no second HEAD
    assert s2["resolved"] == 0 and s2["new"] == 0
    assert "sourcegraph91" in seeds.read_text().split()


async def test_harvest_caches_unresolvable_short_links_too(tmp_path: Path):
    from jobwatch.store import Store
    store = Store(tmp_path / "t.db")
    store.cache_short("abc", None, __import__("datetime").datetime(2026, 9, 4))
    assert store.cached_short({"abc", "xyz"}) == {"abc": None}
