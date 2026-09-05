from __future__ import annotations

import asyncio
import html
import re
from pathlib import Path
from typing import Optional

from .http import Http

ALGOLIA = "https://hn.algolia.com/api/v1"
SEARCH_URL = (
    ALGOLIA + "/search_by_date?query=%22Ask%20HN%3A%20Who%20is%20hiring%3F%22"
    "&tags=story,author_whoishiring&hitsPerPage=200&page={page}"
)
THREAD_TITLE = "Ask HN: Who is hiring?"

GH_PATTERNS = [
    re.compile(r"boards\.greenhouse\.io/embed/job_board\?for=([A-Za-z0-9_-]+)"),
    re.compile(r"(?:boards|job-boards)\.(?:eu\.)?greenhouse\.io/([A-Za-z0-9_-]+)"),
]
OTHER_PATTERNS = [
    re.compile(r"jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_-]+)"),
    re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_.-]+)"),
]
SHORT_PATTERN = re.compile(r"grnh\.se/([A-Za-z0-9]+)")

BLOCKLIST = {
    "embed", "api", "v0", "v1", "static", "assets", "search", "login",
    "about", "privacy", "terms", "jobs", "careers", "job_board",
}
FILE_EXTS = {
    "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "css", "js",
    "html", "htm", "json", "xml", "txt", "pdf",
}


def is_valid_slug(slug: str) -> bool:
    low = slug.lower()
    if len(low) < 2 or low in BLOCKLIST:
        return False
    if "." in low and low.rsplit(".", 1)[1] in FILE_EXTS:
        return False
    return True


def extract_slugs(raw: str) -> set[str]:
    """Run every ATS pattern over the unescaped raw body. Never walks the tree."""
    text = html.unescape(raw)
    found: set[str] = set()
    for pat in GH_PATTERNS + OTHER_PATTERNS:
        found.update(pat.findall(text))
    return {s for s in found if is_valid_slug(s)}


def extract_short_codes(raw: str) -> set[str]:
    return set(SHORT_PATTERN.findall(html.unescape(raw)))


async def resolve_short(http: Http, code: str) -> Optional[str]:
    """HEAD without following; fall back to GET when the shortener won't redirect a HEAD.

    Only a Location on a Greenhouse host yields a slug. Anything else (a
    company's own careers page) is discarded: harvest never guesses.
    """
    url = f"https://grnh.se/{code}"
    resp = await http.head(url)
    if not (300 <= resp.status_code < 400):
        resp = await http.get(url)
    loc = resp.headers.get("location", "")
    for pat in GH_PATTERNS:
        m = pat.search(loc)
        if m and is_valid_slug(m.group(1)):
            return m.group(1)
    return None


async def list_threads(http: Http, months: Optional[int]) -> list[dict]:
    hits: list[dict] = []
    page = 0
    while True:
        status, data = await http.get_json(SEARCH_URL.format(page=page))
        if status != 200 or not data or not data.get("hits"):
            break
        hits.extend(h for h in data["hits"] if (h.get("title") or "").startswith(THREAD_TITLE))
        page += 1
        if page >= int(data.get("nbPages", 1)):
            break
    hits.sort(key=lambda h: h.get("created_at", ""), reverse=True)
    return hits[:months] if months else hits


async def harvest_thread(http: Http, thread_id: str) -> tuple[set[str], set[str]]:
    resp = await http.get(f"{ALGOLIA}/items/{thread_id}")
    if resp.status_code != 200:
        return set(), set()
    return extract_slugs(resp.text), extract_short_codes(resp.text)


def merge_seeds(path: Path, slugs: set[str]) -> tuple[list[str], int]:
    existing = set(path.read_text().split()) if path.exists() else set()
    merged = sorted(existing | slugs)
    path.write_text("\n".join(merged) + ("\n" if merged else ""))
    return merged, len(merged) - len(existing)


async def harvest(http: Http, seeds_path: Path, months: Optional[int] = None) -> dict:
    threads = await list_threads(http, months)
    results = await asyncio.gather(*(harvest_thread(http, h["objectID"]) for h in threads))
    slugs: set[str] = set()
    codes: set[str] = set()
    for s, c in results:
        slugs |= s
        codes |= c
    resolved = await asyncio.gather(*(resolve_short(http, c) for c in sorted(codes)))
    slugs |= {s for s in resolved if s}
    merged, new = merge_seeds(seeds_path, slugs)
    return {
        "threads": len(threads), "slugs": len(slugs), "short_codes": len(codes),
        "new": new, "total": len(merged),
    }
