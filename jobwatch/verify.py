from __future__ import annotations

import asyncio
import json
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


async def verify(http: Http, seeds_path: Path, companies_path: Path, store: Store,
                 dead_days: int = 30, now: Optional[datetime] = None) -> dict:
    now = now or now_utc()
    seeds = [s for s in seeds_path.read_text().split() if s]
    dead = store.dead_slugs(dead_days, now)
    todo = [s for s in seeds if s not in dead]
    results = await asyncio.gather(*(probe(http, s) for s in todo))
    stamp = now.replace(microsecond=0).isoformat()
    companies = []
    for slug, r in zip(todo, results):
        if r:
            companies.append({**r, "verified_at": stamp})
            store.unmark_dead(slug)
        else:
            store.mark_dead(slug, now)
    companies.sort(key=lambda c: c["slug"])
    companies_path.write_text(json.dumps(companies, indent=1) + "\n")
    return {
        "seeds": len(seeds),
        "skipped_dead": len([s for s in seeds if s in dead]),
        "probed": len(todo),
        "confirmed": len(companies),
    }
