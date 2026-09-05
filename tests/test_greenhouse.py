import httpx

from jobwatch.ats import greenhouse
from jobwatch.http import Http
from jobwatch.models import FetchError


def test_parse_unescapes_then_strips(fixture_json):
    posts = greenhouse.parse("stripe", fixture_json("greenhouse_stripe.json"))
    assert len(posts) == 3
    p = posts[0]
    assert p.key == f"greenhouse:stripe:{p.job_id}"
    assert p.title == "Software Engineer, New Grad"
    assert p.company == "Stripe"
    assert "new grads" in p.description and "<" not in p.description and "&lt;" not in p.description
    assert p.posted_at.endswith("+00:00")
    assert p.url.startswith("https://")
    assert p.location == "San Francisco, CA"
    assert p.remote is False


def test_parse_remote_flag_from_location(fixture_json):
    posts = greenhouse.parse("stripe", fixture_json("greenhouse_stripe.json"))
    unknown = [p for p in posts if p.location.lower() in ("n/a", "remote")][0]
    assert unknown.remote in (None, True)
    assert greenhouse._remote("Remote - US") is True
    assert greenhouse._remote("N/A") is None
    assert greenhouse._remote("") is None
    assert greenhouse._remote("Dublin") is False


def make_http(handler):
    return Http(rps=1000, workers=5, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_fetch_uses_content_true_and_raises_on_404(fixture_json):
    def handler(req):
        if req.url.path == "/v1/boards/stripe/jobs":
            assert req.url.params.get("content") == "true"
            return httpx.Response(200, json=fixture_json("greenhouse_stripe.json"))
        return httpx.Response(404, json={"status": 404, "error": "Job not found"})

    posts = await greenhouse.fetch(make_http(handler), "stripe")
    assert len(posts) == 3
    try:
        await greenhouse.fetch(make_http(handler), "nope")
        assert False, "expected FetchError"
    except FetchError as e:
        assert "404" in str(e)


async def test_count_returns_open_roles_and_company_name(fixture_json):
    def handler(req):
        if req.url.path == "/v1/boards/stripe/jobs":
            assert "content" not in req.url.params
            return httpx.Response(200, json=fixture_json("greenhouse_stripe.json"))
        return httpx.Response(404)

    assert await greenhouse.count(make_http(handler), "stripe") == (3, "Stripe")
    assert await greenhouse.count(make_http(handler), "nope") == (0, "nope")
