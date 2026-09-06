from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .ats import ADAPTERS, PROBE_ORDER
from .http import Http
from .store import Store
from .util import now_utc


async def probe(http: Http, slug: str) -> Optional[dict]:
    """First ATS that returns >=1 posting wins. Empty is a miss: it means wrong ATS, no roles, or upstream error."""
    for ats in PROBE_ORDER:
        n, name = await ADAPTERS[ats].count(http, slug)
        if n > 0:
            return {"slug": slug, "ats": ats, "name": name, "open_roles": n}
    return None


def _write(path: Path, companies: list[dict]) -> None:
    # Ashby and Lever answer case-variant slugs for the same board; keep one.
    seen: set[tuple[str, str]] = set()
    kept = []
    for c in sorted(companies, key=lambda c: c["slug"]):
        k = (c["ats"], c["slug"].lower())
        if k not in seen:
            seen.add(k)
            kept.append(c)
    companies[:] = kept
    path.write_text(json.dumps(companies, indent=1) + "\n")


def read_seeds(*paths: Path) -> list[str]:
    """Union of slug files. One slug per line; blank lines and `#` comments are ignored."""
    out: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            slug = line.split("#", 1)[0].strip()
            if slug:
                out.add(slug)
    return sorted(out)


async def verify(http: Http, seeds_path: Path, companies_path: Path, store: Store,
                 dead_days: int = 30, now: Optional[datetime] = None, chunk: int = 100,
                 fresh_days: float = 1.0, manual_path: Optional[Path] = None,
                 only_new: bool = False) -> dict:
    """Probe seeds in chunks; companies.json is rewritten after every chunk so a
    killed run keeps its progress. `manual_path` is a hand-kept slug list merged
    with the harvested one. `only_new` keeps every confirmed company as is and
    probes just the seeds it has never confirmed (the daily rescan)."""
    now = now or now_utc()
    seeds = read_seeds(seeds_path, *([manual_path] if manual_path else []))
    dead = store.dead_slugs(dead_days, now)
    # Resume: entries confirmed within `fresh_days` are kept without re-probing,
    # so a killed run picks up where it stopped. Weekly re-verify is unaffected.
    companies: list[dict] = []
    if companies_path.exists():
        cutoff = "" if only_new else (now - timedelta(days=fresh_days)).replace(microsecond=0).isoformat()
        companies = [c for c in json.loads(companies_path.read_text())
                     if c.get("verified_at", "") >= cutoff and c["slug"] in seeds]
    fresh = {c["slug"] for c in companies}
    todo = [s for s in seeds if s not in dead and s not in fresh]
    stamp = now.replace(microsecond=0).isoformat()
    for i in range(0, len(todo), chunk):
        batch = todo[i:i + chunk]
        results = await asyncio.gather(*(probe(http, s) for s in batch))
        for slug, r in zip(batch, results):
            if r:
                companies.append({**r, "verified_at": stamp})
                store.unmark_dead(slug)
            else:
                store.mark_dead(slug, now)
        _write(companies_path, companies)
        print(f"verify: {min(i + chunk, len(todo))}/{len(todo)} probed, {len(companies)} confirmed",
              file=sys.stderr, flush=True)
    if not todo:
        _write(companies_path, companies)
    return {
        "seeds": len(seeds),
        "skipped_dead": len([s for s in seeds if s in dead]),
        "resumed": len(fresh),
        "probed": len(todo),
        "confirmed": len(companies),
    }
