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


def render(date_str: str, slot: str, funnel: dict, shown: list[dict], unscored: list[dict],
           errors: list[str], now: Optional[datetime] = None) -> str:
    now = now or now_utc()
    lines = [f"# jobwatch {date_str} {slot}", ""]
    lines.append(
        f"fetched {funnel['fetched']} · new {funnel['new']} · stale {funnel['stale']} · "
        f"prefiltered {funnel['prefiltered']} · scored {funnel['scored']} · shown {funnel['shown']}"
    )
    lines.append("")
    if not shown:
        lines.append("No new postings worth showing.")
    for e in shown:
        meta = [e["company"], e.get("location") or "location unknown"]
        age = hours_ago(e.get("posted_at"), now)
        if age:
            meta.append(age)
        if e.get("comp"):
            meta.append(e["comp"])
        lines.append(f"- **{e['score']}** [{e['title']}]({e['url']}) — {' · '.join(meta)}")
        if e.get("reason"):
            lines.append(f"  {e['reason']}")
    if unscored:
        lines += ["", f"## Unscored ({len(unscored)})"]
        lines += [f"- [{u['title']}]({u['url']}) — {u['company']}" for u in unscored]
    if errors:
        lines += ["", f"## Fetch errors ({len(errors)})"]
        lines += [f"- {err}" for err in errors]
    return "\n".join(lines) + "\n"
