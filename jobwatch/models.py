from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class FetchError(Exception):
    """A board could not be fetched. Recorded, never fatal."""


@dataclass
class Posting:
    ats: str
    slug: str
    job_id: str
    title: str
    company: str
    location: str
    remote: Optional[bool]
    description: str
    posted_at: Optional[str]   # ISO 8601 UTC, or None
    url: str
    comp: Optional[str] = None

    @property
    def key(self) -> str:
        return f"{self.ats}:{self.slug}:{self.job_id}"
