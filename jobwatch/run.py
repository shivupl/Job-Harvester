"""The daily pipeline: fetch → diff → stale → prefilter → score → digest → prune."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

from .ats import ADAPTERS
from .digest import render
from .http import Http
from .models import FetchError, Posting
from .prefilter import is_stale, prefilter
from .profile import PROFILE
from .score import score_all
from .store import Store
from .util import now_utc


@dataclass
class RunResult:
    shown: int
    digest_path: Optional[Path]
    baseline: bool
    funnel: dict


async def fetch_all(http: Http, companies: list[dict]) -> tuple[list[Posting], list[str]]:
    async def one(c: dict):
        try:
            return await ADAPTERS[c["ats"]].fetch(http, c["slug"]), None
        except (FetchError, httpx.TransportError, KeyError, ValueError) as e:
            return [], f"{c['ats']}:{c['slug']} — {e}"

    results = await asyncio.gather(*(one(c) for c in companies))
    postings: list[Posting] = []
    errors: list[str] = []
    seen: set[str] = set()
    for posts, err in results:
        if err:
            errors.append(err)
        for p in posts:
            if p.key not in seen:
                seen.add(p.key)
                postings.append(p)
    return postings, errors


async def run(http: Http, store: Store, client, companies_path: Path, digests_dir: Path,
              slot: str, profile: dict = PROFILE, now: Optional[datetime] = None) -> RunResult:
    now = now or now_utc()
    companies = json.loads(companies_path.read_text())
    baseline = store.is_empty()
    funnel = {"fetched": 0, "new": 0, "stale": 0, "prefiltered": 0, "scored": 0, "shown": 0}
    errors: list[str] = []
    survivors: list[Posting] = []
    chunk = profile.get("fetch_chunk", 50)

    # Boards are fetched in chunks and folded into the store immediately, so
    # memory is bounded by one chunk rather than every board's postings.
    for i in range(0, len(companies), chunk):
        postings, errs = await fetch_all(http, companies[i:i + chunk])
        errors.extend(errs)
        funnel["fetched"] += len(postings)
        for p in postings:
            if store.has(p.key):
                continue
            if baseline:
                store.insert(p, "baseline", None, now)
                continue
            funnel["new"] += 1
            if is_stale(p.posted_at, now, profile["max_posting_age_days"]):
                store.insert(p, "stale", "stale", now)
                funnel["stale"] += 1
                continue
            reason = prefilter(p, profile)
            if reason:
                store.insert(p, "dropped", reason, now)
                funnel["prefiltered"] += 1
            else:
                store.insert(p, "unscored", None, now, location=p.location, url=p.url)  # placeholder until scored
                survivors.append(p)

    if baseline:
        store.record_run(now, slot, **funnel)
        return RunResult(0, None, True, funnel)

    results = await score_all(client, survivors, profile) if survivors else {}
    shown: list[dict] = []
    unscored: list[dict] = []
    for p in survivors:
        r = results.get(p.key)
        if r is None:
            unscored.append({"title": p.title, "url": p.url, "company": p.company})
            continue
        funnel["scored"] += 1
        store.update(p.key, status="scored", reason=r["reason"], score=r["score"], level=r["level"],
                     new_grad_fit=r["new_grad_fit"], years_stated=r["years_stated"])
        if r["score"] >= profile["min_score"]:
            shown.append({"score": r["score"], "title": p.title, "url": p.url, "company": p.company,
                          "location": p.location, "posted_at": p.posted_at, "comp": p.comp,
                          "reason": r["reason"]})
    shown.sort(key=lambda d: d["posted_at"] or "", reverse=True)   # newest first...
    shown.sort(key=lambda d: -d["score"])                             # ...within score desc (stable)
    funnel["shown"] = len(shown)

    local_date = now.astimezone(ZoneInfo(profile["timezone"])).strftime("%Y-%m-%d")
    digests_dir.mkdir(parents=True, exist_ok=True)
    path = digests_dir / f"{local_date}-{slot}.md"
    path.write_text(render(local_date, slot, funnel, shown, unscored, errors, now=now))

    store.prune(profile["prune_days"], now)
    store.maybe_vacuum(now)
    store.record_run(now, slot, **funnel)
    return RunResult(len(shown), path, False, funnel)
