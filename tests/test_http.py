import asyncio
import time

import httpx
import pytest

from jobwatch.http import HostLimiter, Http


async def test_limiter_caps_one_host_globally_not_per_worker():
    lim = HostLimiter(rps=50)
    t0 = time.monotonic()
    await asyncio.gather(*(lim.wait("a.example") for _ in range(30)))
    elapsed = time.monotonic() - t0
    assert elapsed >= 29 / 50  # 30 slots spaced 20ms apart


async def test_limiter_buckets_are_independent_per_host():
    lim = HostLimiter(rps=50)
    t0 = time.monotonic()
    await asyncio.gather(
        *(lim.wait("a.example") for _ in range(15)),
        *(lim.wait("b.example") for _ in range(15)),
    )
    elapsed = time.monotonic() - t0
    assert 14 / 50 <= elapsed < 29 / 50


def make_http(handler, **kw):
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, follow_redirects=False)
    return Http(rps=1000, workers=5, client=client, **kw)


async def test_get_json_parses_200_and_returns_none_otherwise():
    def handler(req):
        if req.url.path == "/ok":
            return httpx.Response(200, json={"a": 1})
        return httpx.Response(404, text="Not Found")

    http = make_http(handler)
    assert await http.get_json("https://x.example/ok") == (200, {"a": 1})
    assert await http.get_json("https://x.example/missing") == (404, None)


async def test_retries_on_429_then_succeeds():
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=[])

    http = make_http(handler, retries=3)
    status, data = await http.get_json("https://x.example/p")
    assert status == 200 and data == [] and len(calls) == 2


async def test_gives_up_after_retries_and_returns_last_response():
    def handler(req):
        return httpx.Response(503)

    http = make_http(handler, retries=2)
    http.base_delay = 0
    resp = await http.get("https://x.example/p")
    assert resp.status_code == 503


async def test_head_does_not_follow_redirects():
    def handler(req):
        assert req.method == "HEAD"
        return httpx.Response(301, headers={"Location": "https://job-boards.greenhouse.io/acme"})

    http = make_http(handler)
    resp = await http.head("https://grnh.se/abc")
    assert resp.status_code == 301
    assert resp.headers["location"].endswith("/acme")
