import httpx

from jobwatch.ats import ADAPTERS, ashby
from jobwatch.http import Http


def test_parse_skips_unlisted_and_reads_structured_fields(fixture_json):
    posts = ashby.parse("openai", fixture_json("ashby_openai.json"))
    assert len(posts) == 3                       # 4 in fixture, 1 unlisted
    assert not any(p.title == "Unlisted Confidential Role" for p in posts)
    fde = [p for p in posts if p.title == "Forward Deployed Engineer"][0]
    assert fde.location.startswith("San Francisco")
    assert "California" in fde.location
    assert fde.posted_at.endswith("+00:00")
    assert fde.url == f"https://jobs.ashbyhq.com/openai/{fde.job_id}"
    assert fde.comp and "$" in fde.comp
    assert fde.key == f"ashby:openai:{fde.job_id}"
    remote = [p for p in posts if p.remote is True]
    assert remote


def test_parse_remote_from_workplace_type():
    payload = {"jobs": [{"id": "1", "title": "X", "isListed": True, "isRemote": None,
                         "workplaceType": "Remote", "location": "Anywhere",
                         "secondaryLocations": [{"location": "NYC"}], "publishedAt": "2026-09-01T00:00:00Z",
                         "jobUrl": "u", "descriptionPlain": "d", "compensation": None}]}
    p = ashby.parse("s", payload)[0]
    assert p.remote is True and p.location == "Anywhere, NYC" and p.comp is None


def make_http(handler):
    return Http(rps=1000, workers=5, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_fetch_and_count(fixture_json):
    def handler(req):
        if req.url.path == "/posting-api/job-board/openai":
            return httpx.Response(200, json=fixture_json("ashby_openai.json"))
        return httpx.Response(404, text="Not Found")

    assert len(await ashby.fetch(make_http(handler), "openai")) == 3
    assert await ashby.count(make_http(handler), "openai") == (3, "openai")
    assert await ashby.count(make_http(handler), "Openai") == (0, "Openai")   # case-sensitive
    assert set(ADAPTERS) == {"greenhouse", "lever", "ashby"}


async def test_count_scans_compact_json_without_parsing():
    body = '{"jobs":[{"id":"1","isListed":true},{"id":"2","isListed":false},{"id":"3","isListed":true}]}'

    def handler(req):
        return httpx.Response(200, text=body, headers={"content-type": "application/json"})

    assert await ashby.count(make_http(handler), "x") == (2, "x")
