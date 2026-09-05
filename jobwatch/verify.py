from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
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
    companies.sort(key=lambda c: c["slug"])
    path.write_text(json.dumps(companies, indent=1) + "\n")


async def verify(http: Http, seeds_path: Path, companies_path: Path, store: Store,
                 dead_days: int = 30, now: Optional[datetime] = None, chunk: int = 100) -> dict:
    """Probe seeds in chunks; companies.json is rewritten after every chunk so a
    killed run keeps its progress."""
    now = now or now_utc()
    seeds = [s for s in seeds_path.read_text().split() if s]
    dead = store.dead_slugs(dead_days, now)
    todo = [s for s in seeds if s not in dead]
    stamp = now.replace(microsecond=0).isoformat()
    companies: list[dict] = []
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
        "probed": len(todo),
        "confirmed": len(companies),
    }
