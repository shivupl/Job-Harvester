from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Optional

_TAG = re.compile(r"<[^>]+>")
_BLOCK_END = re.compile(r"</(?:p|div|li|ul|ol|h[1-6]|br|tr)>|<br\s*/?>", re.I)


def strip_tags(s: str) -> str:
    """Strip HTML tags, unescape entities, collapse whitespace. Block ends become newlines."""
    s = _BLOCK_END.sub("\n", s)
    s = _TAG.sub(" ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()


def to_utc_iso(value) -> Optional[str]:
    """Normalize ISO strings (with offset or Z) or epoch milliseconds to ISO UTC, second precision."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        else:
            s = str(value).strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
