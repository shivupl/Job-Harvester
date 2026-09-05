# jobwatch — design spec

Date: 2026-09-04
Status: approved in brainstorming, pending user review of this file

## Outcome

Three times per weekday, a short list of new job postings worth applying to,
delivered as a GitHub issue, without visiting a careers page.

Each digest holds roughly 5–15 roles, each scored with a one-line reason,
drawn from a few thousand startup job boards, containing only postings that
appeared since the previous run and were published on the ATS within the last
14 days.

Success: the digest is read in 60 seconds and produces 1–2 applications.
Failure: the digest is noisy and stops being read. Design against noise.

## Scope

In: Ashby, Greenhouse, Lever. Public JSON APIs only. Hacker News "Who is
hiring?" via the Algolia API as the seed source, including `grnh.se`
short links resolved by redirect.

Out: LinkedIn, Indeed, Workday, HTML scraping, browser automation, paid data,
authenticated endpoints, the YC company directory (evaluated, deferred by
user decision), web UI, config files, env vars beyond `ANTHROPIC_API_KEY`,
user accounts, resume parsing, auto-apply, application tracking, email or
Slack.

If the digest is too noisy, tighten `PROFILE`. Do not add features.

## Verified facts (live probes, 2026-09-04)

- HN Algolia item text escapes `/` as `&#x2F;`. Regexes match nothing until
  the raw JSON string is passed through `html.unescape`. After unescaping,
  the September 2026 thread yields 37 slugs from 238 top-level comments.
- Link hosts in that thread: `jobs.ashbyhq.com` 55, `grnh.se` 16,
  `job-boards.greenhouse.io` 14, `jobs.lever.co` 4. Short links must be
  resolved or a fifth of Greenhouse boards are missed.
- Greenhouse `/v1/boards/{slug}/jobs?content=true`: `content` is
  entity-escaped HTML; `first_published` is the posting date; `updated_at`
  refreshes daily and is useless; `location.name` is the only location field
  and reads "N/A" or "Remote" for remote roles. Missing slug returns 404.
- Lever `/v0/postings/{slug}?mode=json`: bare array; title is `text`;
  `createdAt` is epoch milliseconds; `lists[]` holds requirement bullets
  separate from `descriptionPlain`; `workplaceType` and `country` present;
  `skip`/`limit` pagination works. Default limit is not 100 (310 returned
  with no params), so pagination is defensive. Missing slug returns 404.
- Ashby `/posting-api/job-board/{slug}`: `publishedAt`, `isListed`,
  `isRemote`, `workplaceType`, `employmentType`, `secondaryLocations`,
  `address.postalAddress.addressRegion`, `compensation` all present.
  Slugs are case-sensitive. Missing slug returns 404.
- Probing 588 requests at 30 workers took 15 s with no throttling. That
  rate is the thing to avoid.

## Architecture

One Python package, one SQLite file, three commands.

```
python -m jobwatch harvest   (occasional, laptop)   → seeds.txt
python -m jobwatch verify    (weekly, Actions)      → companies.json
python -m jobwatch run       (3x weekday, Actions)  → digests/<date>-<slot>.md
```

### Package layout

```
jobwatch/
  __main__.py     CLI: harvest | verify | run [--slot morning|midday|evening]
  profile.py      PROFILE dict — every threshold and list lives here
  http.py         async httpx client, per-host token bucket, retry/backoff
  harvest.py      HN Algolia → seeds.txt
  verify.py       seeds.txt → companies.json (+ dead table)
  ats/
    greenhouse.py fetch + normalize
    lever.py      fetch + normalize
    ashby.py      fetch + normalize
  store.py        SQLite schema, diff, prune, audit helpers
  prefilter.py    exclusion filters, returns (keep, reason)
  score.py        Claude scoring with structured outputs
  digest.py       markdown rendering
tests/
  fixtures/       trimmed real responses from each ATS and one HN thread
  test_*.py
.github/workflows/jobwatch.yml
```

Dependencies: Python 3.12, `httpx`, `anthropic`, `pytest`, `pytest-asyncio`.
Stdlib `sqlite3`, `re`, `html`, `json`.

### Normalized posting

```
{job_id, ats, slug, title, company, location, remote, description,
 posted_at, url, comp}
```

`remote` is `True`, `False`, or `None` (unknown). `posted_at` is an ISO
UTC string. `comp` is a display string or `None`.

## Part 1 — harvest

1. `GET hn.algolia.com/api/v1/search_by_date?query="Ask HN: Who is hiring?"
   &tags=story,author_whoishiring&hitsPerPage=200` — paginate until empty.
   ~185 threads exist. `--months N` limits to the newest N; default all.
2. For each thread, `GET hn.algolia.com/api/v1/items/{id}`.
3. `text = html.unescape(response.text)` — on the raw body, not the parsed
   tree. Do not walk `children[]`.
4. Run patterns; capture group 1 is the slug:
   - `boards\.greenhouse\.io/embed/job_board\?for=([A-Za-z0-9_-]+)`
   - `(?:boards|job-boards)\.greenhouse\.io/([A-Za-z0-9_-]+)`
   - `jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_-]+)`
   - `jobs\.ashbyhq\.com/([A-Za-z0-9_.-]+)`
   - `grnh\.se/([A-Za-z0-9]+)` — collect codes, then `HEAD` each with
     redirects followed (per-host limited) and run the Greenhouse patterns
     on the final URL.
5. Blocklist: `embed, api, v0, v1, static, assets, search, login, about,
   privacy, terms, jobs, careers` and any segment containing a `.` followed
   by 2–4 letters at the end (file extension). Ashby slugs may legitimately
   contain dots, so the extension check is on the final segment only.
6. Output: `seeds.txt`, one slug per line, case preserved, deduped
   case-sensitively against existing content, sorted.

Expect 2,000–5,000 unique slugs across the archive.

## Part 2 — verify

For each slug not in the `dead` table with a timestamp under 30 days old,
probe in order:

1. `GET boards-api.greenhouse.io/v1/boards/{slug}/jobs`
2. `GET api.lever.co/v0/postings/{slug}?mode=json&limit=1`, then
   `api.eu.lever.co` on 404
3. `GET api.ashbyhq.com/posting-api/job-board/{slug}`

Record the first ATS returning HTTP 200 with at least one posting. Empty
collections are ambiguous (wrong ATS, zero roles, upstream error) and count
as a miss. A slug that misses all three goes to `dead(slug, checked_at)`.

Slugs are stored flat, never bucketed by ATS. Re-verify weekly re-probes
every confirmed and every expired-dead slug, which is how ATS migrations
are caught.

Rate limiting: 30 async workers share three token buckets, one per ATS
host, each refilling at `PROFILE["probe_rps_per_host"]` (default 3). The
buckets are shared, not per-worker; the global ceiling is 9 req/s. A 429
or 5xx sleeps for `Retry-After` if present, else exponential backoff
starting at 2 s, three attempts. 15k requests complete in ~30 minutes.

Output: `companies.json`, a sorted list of
`{slug, ats, name, open_roles, verified_at}`. `name` is taken from the
ATS response (Greenhouse `company_name`, Ashby/Lever fall back to slug).

## Part 3 — fetch

One request per confirmed board, all boards concurrently behind the same
limiters. A failing board is recorded in `fetch_errors` for the digest
footer; it does not abort the run.

### Greenhouse

`GET boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`

- `description = strip_tags(html.unescape(job["content"]))`. Order matters.
- `location = job["location"]["name"]`; `remote = True` if it contains
  "remote", `None` if "N/A", else `False`.
- `posted_at = first_published`. Never use `updated_at`.
- `url = absolute_url`, `job_id = id`, `company = company_name`.

### Lever

`GET api.lever.co/v0/postings/{slug}?mode=json&skip=K&limit=100`,
repeated until a page shorter than 100. On 404, retry against
`api.eu.lever.co` once, then give up.

- `title = text`.
- `description = descriptionPlain + "\n" + strip_tags(each lists[].content)`
  with each list's `text` heading kept.
- `location` = `categories.location` merged with
  `categories.allLocations[]`, deduped, joined with " / ".
- `remote = workplaceType == "remote"`; `None` if field absent.
- `posted_at = createdAt / 1000` → ISO.
- `url = hostedUrl`, `job_id = id`.

### Ashby

`GET api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true`

- Skip `isListed == False`.
- `description = descriptionPlain` (fall back to `strip_tags(descriptionHtml)`).
- `location` = `location` + `secondaryLocations[].location` +
  `address.postalAddress.addressRegion`, joined.
- `remote = isRemote`; also `True` if `workplaceType == "Remote"`.
- `posted_at = publishedAt`, `url = jobUrl`, `job_id = id`,
  `comp = compensation.compensationTierSummary`.

## Part 4 — diff

SQLite table `seen`:

```
key         TEXT PRIMARY KEY   -- "{ats}:{slug}:{job_id}"
first_seen  TEXT               -- ISO UTC, run time
posted_at   TEXT
title       TEXT
company     TEXT
status      TEXT               -- baseline | stale | dropped | scored | unscored
reason      TEXT               -- prefilter reason, or model reason
location    TEXT               -- surviving rows only
url         TEXT
score       INTEGER
level       TEXT
new_grad_fit REAL
years_stated INTEGER
```

Plus `dead(slug PRIMARY KEY, checked_at)` and
`runs(started_at, slot, fetched, new, stale, prefiltered, scored, shown)`.

Per run:

1. If `seen` is empty, insert every fetched posting with `status=baseline`,
   write the run row, exit without a digest. Print a one-line notice.
2. Otherwise, a fetched key absent from `seen` is new.
3. New postings with `posted_at` older than `PROFILE["max_posting_age_days"]`
   (14) are inserted with `status=stale` and go no further. Missing
   `posted_at` is kept.
4. Survivors go to prefilter, then scoring.
5. Delete rows with `first_seen` older than 90 days. `VACUUM`.

Every row keeps title and company so drops are auditable:

```sql
SELECT reason, COUNT(*) FROM seen WHERE status='dropped' GROUP BY 1 ORDER BY 2 DESC;
SELECT reason, title, company FROM seen WHERE status='dropped' ORDER BY first_seen DESC LIMIT 50;
```

## Part 5 — prefilter

Exclusion only. Every list and threshold is in `PROFILE`. Filters run in
this order; the first failure is the recorded reason.

1. `level_terms` in title, word-bounded, case-insensitive: senior, sr,
   staff, principal, director, head of, vp, lead, manager, intern,
   internship, distinguished, fellow, chief, ii, iii, iv, l4–l8.
   "Product lead" is excluded; "Leadership" is not (word boundary).
2. `function_terms` in title: recruiter, recruiting, account executive,
   account manager, sales development, sdr, bdr, marketing, finance,
   accounting, legal, counsel, paralegal, people, hr, designer, nurse,
   physician, clinician, therapist, controller, payroll, executive
   assistant, office manager. "Sales engineer" and "solutions engineer"
   are not in this list and must pass a unit test.
3. Location. Keep if any of:
   - `remote is True` and the location text does not match
     `non_us_terms` (uk, europe, emea, apac, canada, india, latam, and a
     country list),
   - location matches `bay_area_terms` (san francisco, sf, bay area,
     palo alto, mountain view, menlo park, redwood city, san mateo,
     oakland, berkeley, sunnyvale, san jose, cupertino, santa clara,
     south san francisco, foster city, burlingame),
   - Ashby `addressRegion == "California"`,
   - location is empty, "N/A", or `remote is None` with no city named.
   Otherwise drop with reason `location`.
4. Years of experience. Regex over title + description for
   `(\d+)\s*\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs?)` within 40 characters of
   `experience` or `yoe`. Take the smallest number found. Drop if greater
   than `PROFILE["max_years"]` (3). No match keeps.

## Part 6 — score

Model `claude-haiku-4-5`. Concurrency 5. SDK default retries plus one outer
retry on schema failure. Cost estimate at ~300 postings/day: about $0.70/day.

System prompt (cached with a breakpoint): candidate profile — CS new grad,
two startup internships, targeting product/founding/FDE/solutions/AI
engineering roles, Bay Area or US-remote — and explicit calibration:

- 9–10: clearly open to new grads or 0–2 years, matches target role
  types, location fits.
- 6–8: plausible for a strong new grad; level not stated or "early
  career"; minor location or role-type mismatch.
- 3–5: reads as mid-level despite a neutral title; 3+ years implied by
  responsibilities.
- 0–2: senior in substance, wrong function, or wrong region.
- Penalize implied seniority regardless of title. Do not reward famous
  companies. Treat "founding engineer" as open unless the body says
  otherwise. Use the whole description.

User turn: title, company, location, comp, description truncated to
`PROFILE["max_description_chars"]` (6,000).

Output enforced with structured outputs (`output_config.format`), schema:

```json
{"level": "new_grad|junior|mid|senior|unclear",
 "new_grad_fit": 0.0–1.0,
 "years_stated": integer or null,
 "score": 0–10,
 "reason": "string, max 15 words"}
```

On repeated failure store `status=unscored` and list the posting in the
digest footer. Never drop a survivor silently.

## Part 7 — output

File: `digests/YYYY-MM-DD-{slot}.md`, never overwritten.

```
# jobwatch 2026-09-04 morning
fetched 1420 · new 212 · stale 38 · prefiltered 141 · scored 33 · shown 9

- **9** [Forward Deployed Engineer](url) — Acme · San Francisco · 6h ago · $150K–$190K
  New-grad friendly FDE role, explicitly 0-2 years, on-site SF.
...

## Unscored (2)
- [Title](url) — Company

## Fetch errors (3)
- lever:oldco — 404 both hosts
```

Shown = `score >= PROFILE["min_score"]` (6), sorted by score then
posted_at descending. Persistent fetch errors mean stale slugs; re-run
verify.

## Delivery

`.github/workflows/jobwatch.yml`:

- Triggers: three `schedule` cron lines with comments giving the Pacific
  time (7:00, 12:00, 17:00), `workflow_dispatch` with a `slot` input.
  GitHub cron is UTC; the lines are written for PDT and shift one hour at
  DST changes unless edited.
- `concurrency: {group: jobwatch, cancel-in-progress: false}` so runs
  queue rather than overlap.
- Steps: checkout, setup Python, install, run `verify` if the slot is
  `morning` and the weekday is Monday, run `run --slot <slot>`, `git pull
  --rebase`, commit `jobwatch.db`, `companies.json`, `digests/`, push,
  create an issue titled `jobwatch <date> <slot>` with the digest body
  only if `shown > 0`.
- Secrets: `ANTHROPIC_API_KEY`. The default `GITHUB_TOKEN` creates issues.

Slot is derived from the cron expression via a small mapping in the
workflow, so one cron line changes one slot.

## Error handling

- HTTP: per-host limiter, 429/5xx backoff, 404 is a definitive miss.
- Board fetch failure: recorded, run continues.
- Scoring failure: `unscored`, surfaced.
- Baseline run: no digest, no issue.
- Empty digest: file written with the funnel line, no issue.

## Testing

- Adapter tests on trimmed fixtures for the three data-loss gotchas:
  Greenhouse unescape-then-strip, Lever `lists[]` merged into
  description, Ashby `isListed` skip.
- Harvest test: fixture thread with `&#x2F;` escaping yields expected
  slugs; blocklist and extension rules.
- Rate limiter test: 30 concurrent tasks through a bucket at 3/s must
  take at least N/3 seconds wall-clock.
- Prefilter tests, table-driven: title/location/description in, reason
  out. Includes "Sales Engineer" kept, "Product Lead" dropped,
  "Leadership Program" kept, "5+ years" dropped, "1-3 years" kept.
- Store tests: baseline, new key, stale key, prune.
- Score tests with a fake client returning canned structured output and
  one returning garbage twice.
- No live network in tests.
