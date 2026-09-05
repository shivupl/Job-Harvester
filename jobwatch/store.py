from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union

from .models import Posting

SCHEMA = """
create table if not exists seen (
  key          text primary key,
  first_seen   text not null,
  posted_at    text,
  title        text,
  company      text,
  status       text not null,   -- baseline | stale | dropped | scored | unscored
  reason       text,
  location     text,
  url          text,
  score        integer,       -- legacy single score (pre two-score); unused
  level        text,
  new_grad_fit real,          -- legacy; unused
  years_stated integer,
  fit          integer,
  relevance    integer,
  category     text,
  location_fit text
);
create index if not exists seen_first_seen on seen(first_seen);
create table if not exists dead (
  slug       text primary key,
  checked_at text not null
);
create table if not exists runs (
  started_at  text not null,
  slot        text not null,
  fetched     integer, new integer, stale integer,
  prefiltered integer, scored integer, shown integer
);
create table if not exists meta (
  key   text primary key,
  value text
);
"""

FIELDS = ("location", "url", "score", "level", "new_grad_fit", "years_stated", "status", "reason",
          "fit", "relevance", "category", "location_fit")
# Additive migrations for databases created before a column existed.
MIGRATIONS = [
    ("seen", "fit", "integer"),
    ("seen", "relevance", "integer"),
    ("seen", "category", "text"),
    ("seen", "location_fit", "text"),
]


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


class Store:
    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self.con = sqlite3.connect(str(self.path))
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        self._migrate()
        self.con.commit()

    def _migrate(self) -> None:
        for table, col, typ in MIGRATIONS:
            cols = {r[1] for r in self.con.execute(f"pragma table_info({table})")}
            if col not in cols:
                self.con.execute(f"alter table {table} add column {col} {typ}")

    def close(self) -> None:
        self.con.close()

    # --- seen ---
    def is_empty(self) -> bool:
        return self.con.execute("select count(*) from seen").fetchone()[0] == 0

    def has(self, key: str) -> bool:
        return self.con.execute("select 1 from seen where key=?", (key,)).fetchone() is not None

    def get(self, key: str) -> Optional[sqlite3.Row]:
        return self.con.execute("select * from seen where key=?", (key,)).fetchone()

    def insert(self, p: Posting, status: str, reason: Optional[str], first_seen: datetime, **fields) -> None:
        bad = set(fields) - set(FIELDS)
        if bad:
            raise ValueError(f"unknown fields {bad}")
        cols = ["key", "first_seen", "posted_at", "title", "company", "status", "reason"] + list(fields)
        vals = [p.key, _iso(first_seen), p.posted_at, p.title, p.company, status, reason] + list(fields.values())
        self.con.execute(
            f"insert or replace into seen ({','.join(cols)}) values ({','.join('?' * len(cols))})", vals)
        self.con.commit()

    def update(self, key: str, **fields) -> None:
        bad = set(fields) - set(FIELDS)
        if bad:
            raise ValueError(f"unknown fields {bad}")
        sets = ", ".join(f"{k}=?" for k in fields)
        self.con.execute(f"update seen set {sets} where key=?", list(fields.values()) + [key])
        self.con.commit()

    def release_baseline_since(self, cutoff_iso: str) -> int:
        """Forget baseline rows, and rows dropped for level/location, posted on/after
        cutoff, so a backfill run re-evaluates them under current rules."""
        cur = self.con.execute(
            "delete from seen where posted_at >= ? and (status='baseline' "
            "or (status='dropped' and reason in ('level', 'location')))", (cutoff_iso,))
        self.con.commit()
        return cur.rowcount

    def prune(self, days: int, now: datetime) -> int:
        cutoff = _iso(now - timedelta(days=days))
        cur = self.con.execute("delete from seen where first_seen < ?", (cutoff,))
        self.con.commit()
        return cur.rowcount

    def maybe_vacuum(self, now: datetime) -> bool:
        """VACUUM at most once per calendar month; per-run VACUUM inflates git history."""
        month = now.strftime("%Y-%m")
        row = self.con.execute("select value from meta where key='last_vacuum'").fetchone()
        if row and row[0] == month:
            return False
        self.con.execute("vacuum")
        self.con.execute("insert or replace into meta(key, value) values ('last_vacuum', ?)", (month,))
        self.con.commit()
        return True

    def audit(self) -> list[tuple[str, int]]:
        rows = self.con.execute(
            "select reason, count(*) from seen where status='dropped' group by reason order by 2 desc, 1"
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    # --- dead slugs ---
    def dead_slugs(self, max_age_days: int, now: datetime) -> set[str]:
        cutoff = _iso(now - timedelta(days=max_age_days))
        return {r[0] for r in self.con.execute("select slug from dead where checked_at >= ?", (cutoff,))}

    def mark_dead(self, slug: str, now: datetime) -> None:
        self.con.execute("insert or replace into dead(slug, checked_at) values (?, ?)", (slug, _iso(now)))
        self.con.commit()

    def unmark_dead(self, slug: str) -> None:
        self.con.execute("delete from dead where slug=?", (slug,))
        self.con.commit()

    # --- runs ---
    def record_run(self, started_at: datetime, slot: str, **counts) -> None:
        self.con.execute(
            "insert into runs(started_at, slot, fetched, new, stale, prefiltered, scored, shown) "
            "values (?,?,?,?,?,?,?,?)",
            (_iso(started_at), slot, counts.get("fetched"), counts.get("new"), counts.get("stale"),
             counts.get("prefiltered"), counts.get("scored"), counts.get("shown")))
        self.con.commit()
