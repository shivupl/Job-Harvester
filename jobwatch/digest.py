from __future__ import annotations

from datetime import datetime
from typing import Optional

from .util import now_utc


def hours_ago(posted_at: Optional[str], now: datetime) -> str:
    if not posted_at:
        return ""
    try:
        dt = datetime.fromisoformat(posted_at)
    except ValueError:
        return ""
    hours = int((now - dt).total_seconds() // 3600)
    if hours < 0:
        hours = 0
    if hours < 48:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


CATEGORY_ORDER = [
    ("fde", "FDE & Solutions"),
    ("product", "Product & Strategy"),
    ("applied_ai", "Applied AI"),
    ("swe", "Software Engineering"),
    ("devrel", "DevRel"),
    ("other", "Other"),
]
LOCATION_TAGS = {"bay_area": "Bay Area", "us_remote": "US remote", "other_us": None, "non_us": "non-US", "unknown": None}


def location_tag(e: dict) -> str:
    tag = LOCATION_TAGS.get(e.get("location_fit") or "unknown")
    if tag is None:
        tag = e.get("location") or "location unknown"
    return f"[{tag}]"


def render(date_str: str, slot: str, funnel: dict, shown: list[dict], unscored: list[dict],
           errors: list[str], now: Optional[datetime] = None, stretch_fit: int = 6) -> str:
    now = now or now_utc()
    lines = [f"# jobwatch {date_str} {slot}", ""]
    lines.append(
        f"fetched {funnel['fetched']} · new {funnel['new']} · stale {funnel['stale']} · "
        f"prefiltered {funnel['prefiltered']} · scored {funnel['scored']} · shown {funnel['shown']}"
    )
    lines.append("")
    lines.append("_New since the last run. For everything currently open, sorted and filterable: "
                 "`git pull && python -m jobwatch board --open`._")
    lines.append("")
    if not shown:
        lines.append("No new postings worth showing.")
    by_cat: dict[str, list[dict]] = {}
    for e in shown:
        by_cat.setdefault(e.get("category") or "other", []).append(e)
    for key, header in CATEGORY_ORDER:
        entries = by_cat.get(key)
        if not entries:
            continue
        lines += [f"## {header} ({len(entries)})", ""]
        for e in entries:
            meta = [e["company"], location_tag(e)]
            if e.get("location_fit") in ("bay_area", "us_remote") and e.get("location"):
                meta.append(e["location"])
            age = hours_ago(e.get("posted_at"), now)
            if age:
                meta.append(age)
            if e.get("comp"):
                meta.append(e["comp"])
            if e.get("fit", 10) < stretch_fit:
                meta.append("stretch")
            lines.append(f"- **rel {e['relevance']} · fit {e['fit']}** [{e['title']}]({e['url']}) — {' · '.join(meta)}")
            if e.get("reason"):
                lines.append(f"  {e['reason']}")
        lines.append("")
    if unscored:
        lines += [f"## Unscored ({len(unscored)})"]
        lines += [f"- [{u['title']}]({u['url']}) — {u['company']}" for u in unscored]
        lines.append("")
    if errors:
        lines += [f"## Fetch errors ({len(errors)})"]
        lines += [f"- {err}" for err in errors]
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
