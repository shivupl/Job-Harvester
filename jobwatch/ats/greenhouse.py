"""Greenhouse Job Board API. Thinnest of the three: one free-text location, HTML content."""
from __future__ import annotations

import html
from typing import Optional

from ..http import Http
from ..models import FetchError, Posting
from ..util import strip_tags, to_utc_iso

API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def _remote(location: str) -> Optional[bool]:
    low = location.strip().lower()
    if low in ("", "n/a"):
        return None
    return "remote" in low


def parse(slug: str, payload) -> list[Posting]:
    out: list[Posting] = []
    for j in (payload or {}).get("jobs", []):
        loc = ((j.get("location") or {}).get("name") or "").strip()
        content = j.get("content") or ""
        out.append(Posting(
            ats="greenhouse",
            slug=slug,
            job_id=str(j["id"]),
            title=(j.get("title") or "").strip(),
            company=j.get("company_name") or slug,
            location=loc,
            remote=_remote(loc),
            description=strip_tags(html.unescape(content)),  # unescape FIRST
            posted_at=to_utc_iso(j.get("first_published")),
            url=j.get("absolute_url") or "",
            comp=None,
        ))
    return out


async def fetch(http: Http, slug: str) -> list[Posting]:
    status, data = await http.get_json(API.format(slug=slug) + "?content=true")
    if status != 200 or data is None:
        raise FetchError(f"greenhouse:{slug} HTTP {status}")
    return parse(slug, data)


async def count(http: Http, slug: str) -> tuple[int, str]:
    try:
        status, data = await http.get_json(API.format(slug=slug))
    except Exception:
        return 0, slug
    if status != 200 or not data:
        return 0, slug
    jobs = data.get("jobs") or []
    name = (jobs[0].get("company_name") if jobs else None) or slug
    return len(jobs), name
