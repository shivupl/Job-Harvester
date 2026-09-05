import httpx

from jobwatch.ats import ADAPTERS, lever
from jobwatch.http import Http
from jobwatch.models import FetchError


def test_parse_title_lists_location_and_created_at(fixture_json):
    posts = lever.parse("palantir", fixture_json("lever_palantir.json"))
    assert len(posts) == 2
    p = posts[1]
    assert "Software Engineer" in p.title            # title comes from `text`
    assert "3+ years of experience" in p.description  # lists[] merged in
    assert "What We Require" in p.description
    assert "<li>" not in p.description
    assert p.posted_at.endswith("+00:00")
    assert p.url.startswith("https://jobs.lever.co/palantir/")
    a = posts[0]
    assert a.location == "London, United Kingdom"
    assert a.remote is False                          # workplaceType hybrid
    assert a.company == "palantir"


def test_parse_merges_all_locations():
    payload = [{"id": "1", "text": "X", "createdAt": 1711403416463, "hostedUrl": "u",
                "categories": {"location": "SF", "allLocations": ["SF", "Remote - US"]},
                "workplaceType": "remote", "descriptionPlain": "d", "lists": []}]
    p = lever.parse("s", payload)[0]
    assert p.location == "SF / Remote - US"
    assert p.remote is True


def make_http(handler):
    return Http(rps=1000, workers=5, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def make_job(i):
    return {"id": str(i), "text": f"Job {i}", "createdAt": 1711403416463, "hostedUrl": "u",
            "categories": {}, "descriptionPlain": "d", "lists": []}


async def test_fetch_paginates_until_short_page():
    def handler(req):
        skip = int(req.url.params.get("skip", "0"))
        assert req.url.params.get("limit") == "100"
        if skip == 0:
            return httpx.Response(200, json=[make_job(i) for i in range(100)])
        if skip == 100:
            return httpx.Response(200, json=[make_job(i) for i in range(100, 110)])
        return httpx.Response(200, json=[])

    posts = await lever.fetch(make_http(handler), "big")
    assert len(posts) == 110


async def test_fetch_falls_back_to_eu_host_then_raises():
    hosts = []

    def handler(req):
        hosts.append(req.url.host)
        if req.url.host == "api.eu.lever.co":
            return httpx.Response(200, json=[make_job(1)])
        return httpx.Response(404, json={"ok": False, "error": "Document not found"})

    posts = await lever.fetch(make_http(handler), "euco")
    assert len(posts) == 1 and hosts == ["api.lever.co", "api.eu.lever.co"]

    def all404(req):
        return httpx.Response(404)

    try:
        await lever.fetch(make_http(all404), "gone")
        assert False
    except FetchError as e:
        assert "both hosts" in str(e)


async def test_count():
    def handler(req):
        if req.url.host == "api.lever.co":
            return httpx.Response(200, json=[make_job(1), make_job(2)])
        return httpx.Response(404)

    assert await lever.count(make_http(handler), "x") == (2, "x")
    assert "lever" in ADAPTERS
