from __future__ import annotations

import asyncio
import time
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx

USER_AGENT = "jobwatch/0.1 (personal job digest; polite, rate-limited)"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class HostLimiter:
    """Spaces requests to each hostname at most `rps` per second.

    One reservation ledger per host, shared by every caller. Callers reserve
    the next free slot under a lock, then sleep until it arrives, so N
    concurrent workers never exceed the per-host rate.
    """

    def __init__(self, rps: float):
        self.interval = 1.0 / rps
        self._next: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, host: str) -> None:
        async with self._lock:
            now = time.monotonic()
            slot = max(now, self._next.get(host, now))
            self._next[host] = slot + self.interval
        delay = slot - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)


class Http:
    def __init__(
        self,
        rps: float = 3.0,
        workers: int = 30,
        retries: int = 3,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 30.0,
    ):
        self.limiter = HostLimiter(rps)
        self.sem = asyncio.Semaphore(workers)
        self.retries = retries
        self.base_delay = 2.0
        self.client = client or httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=False,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    def _retry_delay(self, resp: Optional[httpx.Response], attempt: int) -> float:
        if resp is not None:
            ra = resp.headers.get("retry-after")
            if ra and ra.isdigit():
                return float(ra)
        return self.base_delay * (2 ** attempt)

    async def request(self, method: str, url: str, **kw) -> httpx.Response:
        host = urlsplit(url).hostname or url
        resp: Optional[httpx.Response] = None
        last_exc: Optional[Exception] = None
        for attempt in range(self.retries):
            async with self.sem:
                await self.limiter.wait(host)
                try:
                    resp = await self.client.request(method, url, **kw)
                    last_exc = None
                except httpx.TransportError as e:
                    resp, last_exc = None, e
            if resp is not None and resp.status_code not in RETRY_STATUSES:
                return resp
            if attempt < self.retries - 1:
                await asyncio.sleep(self._retry_delay(resp, attempt))
        if resp is not None:
            return resp
        assert last_exc is not None
        raise last_exc

    async def get(self, url: str, **kw) -> httpx.Response:
        return await self.request("GET", url, **kw)

    async def head(self, url: str) -> httpx.Response:
        return await self.request("HEAD", url)

    async def get_json(self, url: str) -> tuple[int, Any]:
        resp = await self.get(url)
        if resp.status_code != 200:
            return resp.status_code, None
        try:
            return 200, resp.json()
        except ValueError:
            return 200, None
