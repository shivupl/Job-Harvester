"""Lever Postings API. Bare array, `text` is the title, requirements live in lists[]."""
from __future__ import annotations

from typing import Any

from ..http import Http
from ..models import FetchError, Posting
from ..util import strip_tags, to_utc_iso

HOSTS = ["https://api.lever.co", "https://api.eu.lever.co"]
PAGE = 100


def parse(slug: str, payload) -> list[Posting]:
    out: list[Posting] = []
    for j in payload or []:
        cats = j.get("categories") or {}
        locs: list[str] = []
        for loc in [cats.get("location")] + list(cats.get("allLocations") or []):
            if loc and loc not in locs:
                locs.append(loc)
        parts = [j.get("descriptionPlain") or strip_tags(j.get("description") or "")]
        for lst in j.get("lists") or []:
            parts.append(f"{lst.get('text', '')}\n{strip_tags(lst.get('content') or '')}")
        wt = (j.get("workplaceType") or "").lower()
        remote = None if not wt else wt == "remote"
        out.append(Posting(
            ats="lever",
            slug=slug,
            job_id=str(j["id"]),
            title=(j.get("text") or "").strip(),
            company=slug,
            location=" / ".join(locs),
            remote=remote,
            description="\n".join(parts),
            posted_at=to_utc_iso(j.get("createdAt")),
            url=j.get("hostedUrl") or "",
            comp=None,
        ))
    return out


async def _page(http: Http, host: str, slug: str, skip: int) -> tuple[int, Any]:
    return await http.get_json(f"{host}/v0/postings/{slug}?mode=json&skip={skip}&limit={PAGE}")


async def fetch(http: Http, slug: str) -> list[Posting]:
    for host in HOSTS:
        status, data = await _page(http, host, slug, 0)
        if status == 404:
            continue
        if status != 200 or not isinstance(data, list):
            raise FetchError(f"lever:{slug} HTTP {status}")
        items = list(data)
        skip = PAGE
        while len(data) == PAGE:
            status, data = await _page(http, host, slug, skip)
            if status != 200 or not isinstance(data, list):
                break
            items.extend(data)
            skip += PAGE
        return parse(slug, items)
    raise FetchError(f"lever:{slug} 404 both hosts")


async def count(http: Http, slug: str) -> tuple[int, str]:
    for host in HOSTS:
        try:
            status, data = await _page(http, host, slug, 0)
        except Exception:
            return 0, slug
        if status == 200 and isinstance(data, list):
            return len(data), slug
    return 0, slug
