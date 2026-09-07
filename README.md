# jobwatch

Three times per weekday: new startup job postings from Greenhouse, Lever, and
Ashby boards, scored for one candidate, delivered as a GitHub issue.

Design: `docs/superpowers/specs/2026-09-04-jobwatch-design.md`.
Preferences: `jobwatch/profile.py`. There is no other configuration.

## One-time setup (laptop)

    python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
    echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env        # .env is git-ignored
    .venv/bin/python -m pytest -q

    .venv/bin/python -m jobwatch harvest              # all HN threads → seeds.txt (~200 requests)
    .venv/bin/python -m jobwatch verify               # seeds.txt + seeds-manual.txt → companies.json (~30 min, rate-limited)
    .venv/bin/python -m jobwatch run                  # first run is a silent baseline
    git add seeds.txt companies.json jobwatch.db && git commit -m "baseline"

Then push to GitHub, add `ANTHROPIC_API_KEY` under Settings → Secrets → Actions,
and the workflow takes over. Verify re-runs every Monday morning.

## Day to day

    .venv/bin/python -m jobwatch refresh            # git pull, rebuild board.html, open it

## Adjusting

- Slots: edit the three cron lines in `.github/workflows/jobwatch.yml` and the
  matching `case` lines in the slot step.
- Too noisy: tighten lists in `jobwatch/profile.py` or raise `min_score`.
- Audit what the prefilter killed:

      sqlite3 jobwatch.db "select reason, count(*) from seen where status='dropped' group by 1 order by 2 desc"
      sqlite3 jobwatch.db "select reason, title, company from seen where status='dropped' order by first_seen desc limit 50"

- Add a company you found elsewhere: put its board slug (the last path segment of
  its Greenhouse, Lever, or Ashby URL) on a line in `seeds-manual.txt`. The next
  morning run probes it; `python -m jobwatch verify --only-new` does it now.
  Write `slug@ashby` to pin one ATS when another still answers with a stub.
- New HN companies arrive on their own: every weekday morning the workflow re-reads
  the newest two "Who is hiring?" threads and probes any slug it hasn't confirmed.
- Persistent fetch errors in a digest footer mean stale slugs: run verify.
