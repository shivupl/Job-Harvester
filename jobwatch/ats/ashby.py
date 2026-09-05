"""Ashby Job Posting API. Richest of the three; slugs are case-sensitive."""
from __future__ import annotations

from ..http import Http
from ..models import FetchError, Posting
from ..util import strip_tags, to_utc_iso

API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def parse(slug: str, payload) -> list[Posting]:
    out: list[Posting] = []
    for j in (payload or {}).get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs: list[str] = []
        candidates = [j.get("location")] + [s.get("location") for s in j.get("secondaryLocations") or []]
        region = ((j.get("address") or {}).get("postalAddress") or {}).get("addressRegion")
        candidates.append(region)
        for loc in candidates:
            if loc and loc not in locs:
                locs.append(loc)
        remote = j.get("isRemote")
        if (j.get("workplaceType") or "") == "Remote":
            remote = True
        comp = (j.get("compensation") or {}).get("compensationTierSummary") or None
        out.append(Posting(
            ats="ashby",
            slug=slug,
            job_id=str(j["id"]),
            title=(j.get("title") or "").strip(),
            company=slug,
            location=", ".join(locs),
            remote=remote,
            description=j.get("descriptionPlain") or strip_tags(j.get("descriptionHtml") or ""),
            posted_at=to_utc_iso(j.get("publishedAt")),
            url=j.get("jobUrl") or "",
            comp=comp,
        ))
    return out


async def fetch(http: Http, slug: str) -> list[Posting]:
    status, data = await http.get_json(API.format(slug=slug) + "?includeCompensation=true")
    if status != 200 or data is None:
        raise FetchError(f"ashby:{slug} HTTP {status}")
    return parse(slug, data)


async def count(http: Http, slug: str) -> tuple[int, str]:
    """Count listed jobs by scanning the raw body. A full board can be 13 MB and
    parsing it into objects costs ~100 MB; the probe only needs a number."""
    try:
        resp = await http.get(API.format(slug=slug))
    except Exception:
        return 0, slug
    if resp.status_code != 200:
        return 0, slug
    text = resp.text
    return text.count('"isListed":true') + text.count('"isListed": true'), slug
