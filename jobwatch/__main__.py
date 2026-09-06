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
    # Accept a bare API_KEY= line as an alias for what the SDK reads.
    if "ANTHROPIC_API_KEY" not in os.environ and os.environ.get("API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = os.environ["API_KEY"]


def make_http() -> Http:
    return Http(rps=PROFILE["probe_rps_per_host"], workers=PROFILE["workers"], retries=PROFILE["http_retries"])


async def cmd_harvest(args) -> dict:
    from .harvest import harvest
    http, store = make_http(), Store(args.db)
    try:
        return await harvest(http, Path(args.seeds), months=args.months, store=store)
    finally:
        await http.aclose()
        store.close()


async def cmd_verify(args) -> dict:
    from .verify import verify
    http, store = make_http(), Store(args.db)
    try:
        return await verify(http, Path(args.seeds), Path(args.companies), store, dead_days=PROFILE["dead_slug_days"],
                            manual_path=Path(args.manual), only_new=args.only_new)
    finally:
        await http.aclose()
        store.close()


async def cmd_run(args) -> dict:
    from .run import run
    from .score import make_client
    if not Path(args.companies).exists():
        sys.exit(f"{args.companies} not found: run `python -m jobwatch verify` first")
    http, store = make_http(), Store(args.db)
    client = make_client()
    try:
        r = await run(http, store, client, Path(args.companies), Path(args.digests), args.slot,
                      backfill_days=args.backfill_days, board_path=Path(args.board),
                      rescore=args.rescore)
    finally:
        await http.aclose()
        store.close()
    out = {"baseline": r.baseline, "digest": str(r.digest_path) if r.digest_path else None, **r.funnel}
    print(f"SHOWN={r.shown}")
    print(f"DIGEST={r.digest_path or ''}")
    return out


async def cmd_enrich(args) -> dict:
    from .run import enrich, write_board
    http, store = make_http(), Store(args.db)
    try:
        out = await enrich(http, store, Path(args.companies))
        out["board_rows"] = write_board(store, Path(args.board))
        return out
    finally:
        await http.aclose()
        store.close()


async def cmd_board(args) -> dict:
    from .run import write_board
    store = Store(args.db)
    try:
        n = write_board(store, Path(args.out))
    finally:
        store.close()
    if args.open:
        import webbrowser
        webbrowser.open(Path(args.out).resolve().as_uri())
    return {"rows": n, "board": args.out}


def main(argv=None) -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="jobwatch")
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("harvest", help="HN 'Who is hiring' threads → seeds.txt")
    h.add_argument("--months", type=int, default=None, help="newest N threads (default: all)")
    h.add_argument("--seeds", default="seeds.txt")
    h.add_argument("--db", default="jobwatch.db", help="caches grnh.se link resolution")
    h.set_defaults(fn=cmd_harvest)

    v = sub.add_parser("verify", help="seeds.txt + seeds-manual.txt → companies.json")
    v.add_argument("--seeds", default="seeds.txt")
    v.add_argument("--manual", default="seeds-manual.txt", help="hand-kept slugs, '#' comments allowed")
    v.add_argument("--only-new", action="store_true",
                   help="probe only seeds not yet in companies.json; keep the rest untouched")
    v.add_argument("--companies", default="companies.json")
    v.add_argument("--db", default="jobwatch.db")
    v.set_defaults(fn=cmd_verify)

    r = sub.add_parser("run", help="fetch, diff, score, digest")
    r.add_argument("--slot", choices=["morning", "midday", "evening", "manual"], default="manual")
    r.add_argument("--companies", default="companies.json")
    r.add_argument("--db", default="jobwatch.db")
    r.add_argument("--digests", default="digests")
    r.add_argument("--backfill-days", type=int, default=None,
                   help="one-off: re-score baseline postings from the last N days")
    r.add_argument("--board", default="board.html")
    r.add_argument("--rescore", action="store_true",
                   help="with --backfill-days: also re-judge already-scored postings (model change)")
    r.set_defaults(fn=cmd_run)

    e = sub.add_parser("enrich", help="one-off: fill comp/excerpt for older scored rows by re-fetching boards")
    e.add_argument("--db", default="jobwatch.db")
    e.add_argument("--companies", default="companies.json")
    e.add_argument("--board", default="board.html")
    e.set_defaults(fn=cmd_enrich)

    b = sub.add_parser("board", help="rebuild board.html from the local database (no network)")
    b.add_argument("--db", default="jobwatch.db")
    b.add_argument("--out", default="board.html")
    b.add_argument("--open", action="store_true", help="open it in your browser")
    b.set_defaults(fn=cmd_board)

    args = ap.parse_args(argv)
    summary = asyncio.run(args.fn(args))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
