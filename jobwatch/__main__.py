from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from .http import Http
from .profile import PROFILE
from .store import Store


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def make_http() -> Http:
    return Http(rps=PROFILE["probe_rps_per_host"], workers=PROFILE["workers"], retries=PROFILE["http_retries"])


async def cmd_harvest(args) -> dict:
    from .harvest import harvest
    http = make_http()
    try:
        return await harvest(http, Path(args.seeds), months=args.months)
    finally:
        await http.aclose()


async def cmd_verify(args) -> dict:
    from .verify import verify
    http, store = make_http(), Store(args.db)
    try:
        return await verify(http, Path(args.seeds), Path(args.companies), store, dead_days=PROFILE["dead_slug_days"])
    finally:
        await http.aclose()
        store.close()


async def cmd_run(args) -> dict:
    import anthropic
    from .run import run
    if not Path(args.companies).exists():
        sys.exit(f"{args.companies} not found: run `python -m jobwatch verify` first")
    http, store = make_http(), Store(args.db)
    client = anthropic.AsyncAnthropic()
    try:
        r = await run(http, store, client, Path(args.companies), Path(args.digests), args.slot)
    finally:
        await http.aclose()
        store.close()
    out = {"baseline": r.baseline, "digest": str(r.digest_path) if r.digest_path else None, **r.funnel}
    print(f"SHOWN={r.shown}")
    print(f"DIGEST={r.digest_path or ''}")
    return out


def main(argv=None) -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="jobwatch")
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("harvest", help="HN 'Who is hiring' threads → seeds.txt")
    h.add_argument("--months", type=int, default=None, help="newest N threads (default: all)")
    h.add_argument("--seeds", default="seeds.txt")
    h.set_defaults(fn=cmd_harvest)

    v = sub.add_parser("verify", help="seeds.txt → companies.json")
    v.add_argument("--seeds", default="seeds.txt")
    v.add_argument("--companies", default="companies.json")
    v.add_argument("--db", default="jobwatch.db")
    v.set_defaults(fn=cmd_verify)

    r = sub.add_parser("run", help="fetch, diff, score, digest")
    r.add_argument("--slot", choices=["morning", "midday", "evening", "manual"], default="manual")
    r.add_argument("--companies", default="companies.json")
    r.add_argument("--db", default="jobwatch.db")
    r.add_argument("--digests", default="digests")
    r.set_defaults(fn=cmd_run)

    args = ap.parse_args(argv)
    summary = asyncio.run(args.fn(args))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
