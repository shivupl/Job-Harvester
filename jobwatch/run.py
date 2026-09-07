"""The daily pipeline: fetch → diff → stale → prefilter → score → digest → prune."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

from .ats import ADAPTERS
from .board import render_board
from .digest import render
from .http import Http
from .models import FetchError, Posting
from .prefilter import is_stale, prefilter
from .profile import PROFILE
from .score import score_all
from .store import EXCERPT_CHARS, Store
from .util import now_utc


async def enrich(http: Http, store: Store, companies_path: Path, profile: dict = PROFILE) -> dict:
    """One-off: fill comp and description excerpts for scored rows written before those
    columns existed. Re-fetches boards (free); no model calls."""
    missing = store.keys_missing_details()
    if not missing:
        return {"missing": 0, "filled": 0, "errors": 0}
    companies = json.loads(companies_path.read_text())
    filled = 0
    errors = 0
    chunk = profile.get("fetch_chunk", 50)
    for i in range(0, len(companies), chunk):
        postings, errs = await fetch_all(http, companies[i:i + chunk])
        errors += len(errs)
        for p in postings:
            if p.key in missing:
                store.set_details(p.key, p.comp, p.description[:EXCERPT_CHARS])
                filled += 1
    return {"missing": len(missing), "filled": filled, "errors": errors}


def write_board(store: Store, path: Path, profile: dict = PROFILE, now: Optional[datetime] = None) -> int:
    """Regenerate board.html from the store. Returns the row count."""
    now = now or now_utc()
    rows = store.board_rows(profile, now)
    path.write_text(render_board(rows, now, profile))
    return len(rows)


async def archive(http: Http, store: Store, client, companies_path: Path, board_path: Path,
                  profile: dict = PROFILE, now: Optional[datetime] = None) -> dict:
    """One-off: score the still-open postings that were too old to score when first seen,
    and write them to a separate board. Rows become status 'archived'; the daily board,
    digest, and runs are untouched."""
    now = now or now_utc()
    companies = json.loads(companies_path.read_text())
    stale = store.stale_keys()
    funnel = {"stale": len(stale), "prefiltered": 0, "scored": 0, "shown": 0}
    survivors: list[Posting] = []
    chunk = profile.get("fetch_chunk", 50)
    for i in range(0, len(companies), chunk):
        postings, _ = await fetch_all(http, companies[i:i + chunk])
        for p in postings:
            if p.key not in stale:
                continue
            if prefilter(p, profile):
                funnel["prefiltered"] += 1          # stays 'stale'; nothing to look at
                continue
            store.update(p.key, location=p.location, url=p.url, comp=p.comp, excerpt=p.description[:EXCERPT_CHARS])
            survivors.append(p)
    results = await score_all(client, survivors, profile) if survivors else {}
    for p in survivors:
        r = results.get(p.key)
        if r is None:
            continue
        funnel["scored"] += 1
        store.update(p.key, status="archived", reason=r["reason"], fit=r["fit"], relevance=r["relevance"],
                     level=r["level"], category=r["category"], location_fit=r["location_fit"],
                     years_stated=r["years_stated"], comp=p.comp or r.get("comp"))
    rows = store.archive_rows(profile)
    board_path.write_text(render_board(rows, now, profile, archive=True))
    funnel["shown"] = len(rows)
    return funnel


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
              slot: str, profile: dict = PROFILE, now: Optional[datetime] = None,
              backfill_days: Optional[int] = None, board_path: Optional[Path] = None,
              rescore: bool = False) -> RunResult:
    now = now or now_utc()
    companies = json.loads(companies_path.read_text())
    max_age = profile["max_posting_age_days"]
    if backfill_days:
        # One-off: re-score baseline postings from the last N days and widen the
        # stale gate to match, so the first digest isn't empty.
        cutoff = (now - timedelta(days=backfill_days)).replace(microsecond=0).isoformat()
        store.release_baseline_since(cutoff, rescore=rescore)
        max_age = max(max_age, backfill_days)
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
            if is_stale(p.posted_at, now, max_age):
                store.insert(p, "stale", "stale", now)
                funnel["stale"] += 1
                continue
            reason = prefilter(p, profile)
            if reason:
                store.insert(p, "dropped", reason, now, location=p.location)
                funnel["prefiltered"] += 1
            else:
                store.insert(p, "unscored", None, now, location=p.location, url=p.url,   # placeholder until scored
                             comp=p.comp, excerpt=p.description[:EXCERPT_CHARS])
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
        comp = p.comp or r.get("comp")            # ATS-structured pay first, else what the model read
        store.update(p.key, status="scored", reason=r["reason"], fit=r["fit"], relevance=r["relevance"],
                     level=r["level"], category=r["category"], location_fit=r["location_fit"],
                     years_stated=r["years_stated"], comp=comp)
        if (r["relevance"] >= profile["min_relevance"] and r["fit"] >= profile["min_fit"]
                and r["location_fit"] not in profile.get("hide_location_fits", [])):
            shown.append({"fit": r["fit"], "relevance": r["relevance"], "category": r["category"],
                          "location_fit": r["location_fit"], "title": p.title, "url": p.url,
                          "company": p.company, "location": p.location, "posted_at": p.posted_at,
                          "comp": comp, "reason": r["reason"]})
    shown.sort(key=lambda d: d["posted_at"] or "", reverse=True)          # newest first...
    shown.sort(key=lambda d: (-d["relevance"], -d["fit"]))                 # ...within relevance, fit (stable)
    funnel["shown"] = len(shown)

    local_date = now.astimezone(ZoneInfo(profile["timezone"])).strftime("%Y-%m-%d")
    digests_dir.mkdir(parents=True, exist_ok=True)
    path = digests_dir / f"{local_date}-{slot}.md"
    path.write_text(render(local_date, slot, funnel, shown, unscored, errors, now=now,
                           stretch_fit=profile["stretch_fit"]))
    write_board(store, board_path or digests_dir.parent / "board.html", profile, now)

    store.prune(profile["prune_days"], now)
    store.maybe_vacuum(now)
    store.record_run(now, slot, **funnel)
    return RunResult(len(shown), path, False, funnel)
