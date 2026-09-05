"""Every threshold and list the pipeline uses. Edit this file, nothing else."""
from __future__ import annotations

PROFILE = {
    # --- HTTP ---
    "probe_rps_per_host": 3.0,     # shared per-hostname ceiling, all workers
    "workers": 8,                  # in-flight requests; more just holds more bodies in RAM at 3 rps/host
    "http_retries": 3,
    # --- verify ---
    "dead_slug_days": 30,          # skip re-probing a dead slug for this long
    # --- diff ---
    "max_posting_age_days": 14,    # older postings are 'stale', never scored
    "prune_days": 90,
    "fetch_chunk": 50,             # boards fetched per batch; bounds memory
    "timezone": "America/Los_Angeles",
    # --- prefilter ---
    "max_years": 3,
    "level_terms": [
        "senior", "sr", "staff", "principal", "director", "head of", "vp",
        "distinguished", "fellow", "chief", "intern", "internship",
        "ii", "iii", "iv", "l4", "l5", "l6", "l7", "l8",
        # phrases replacing bare "manager" and "lead"
        "engineering manager", "general manager", "group manager",
        "program manager", "project manager", "senior manager",
        "tech lead", "team lead", "technical lead", "engineering lead",
    ],
    # Skips the level check only. Function, location, years still apply,
    # so "Associate Counsel" and "Associate Recruiter" stay dropped.
    "early_career_bypass": [
        "associate", "new grad", "new graduate", "entry level", "entry-level",
        "early career", "early-career", "university", "graduate", "college grad",
        "junior", "rotational", "cohort", "apprentice", "i",   # word-bounded: "Engineer I"
    ],
    "function_terms": [
        "recruiter", "recruiting", "account executive", "account manager",
        "sales development", "sdr", "bdr", "marketing", "finance",
        "accounting", "legal", "counsel", "paralegal", "people", "hr",
        "designer", "nurse", "physician", "clinician", "therapist",
        "controller", "payroll", "executive assistant", "office manager",
    ],
    "bay_area_terms": [
        "san francisco", "sf", "bay area", "palo alto", "mountain view",
        "menlo park", "redwood city", "san mateo", "oakland", "berkeley",
        "sunnyvale", "san jose", "cupertino", "santa clara",
        "south san francisco", "foster city", "burlingame", "san carlos",
        "fremont", "san bruno", "daly city", "emeryville", "alameda",
        "hayward", "milpitas", "los altos", "los gatos", "campbell",
        "san leandro", "pleasanton", "walnut creek", "san rafael",
    ],
    # Any of these marks a posting as US-inclusive, which beats a non-US term
    # ("USA, Chile, UK" is kept). Ambiguous state codes count only when no
    # non-US term is present ("Toronto, CA" still drops).
    "us_terms": ["united states", "usa", "u.s.", "u.s.a", "america", "us"],
    "us_states": [
        "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
        "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
        "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
        "maine", "maryland", "massachusetts", "michigan", "minnesota",
        "mississippi", "missouri", "montana", "nebraska", "nevada",
        "new hampshire", "new jersey", "new mexico", "new york",
        "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
        "pennsylvania", "rhode island", "south carolina", "south dakota",
        "tennessee", "texas", "utah", "vermont", "virginia", "washington",
        "west virginia", "wisconsin", "wyoming", "washington dc", "d.c.",
        "al", "ak", "az", "ar", "ca", "co", "ct", "dc", "fl", "ga", "id",
        "il", "ia", "ks", "ky", "la", "md", "ma", "mi", "mn", "ms", "mo",
        "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "ok", "pa",
        "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
    ],
    "non_us_terms": [
        "uk", "united kingdom", "london", "europe", "emea", "apac", "canada",
        "toronto", "vancouver", "india", "bangalore", "bengaluru", "latam",
        "germany", "berlin", "france", "paris", "netherlands", "amsterdam",
        "ireland", "dublin", "spain", "portugal", "lisbon", "poland", "israel",
        "tel aviv", "singapore", "australia", "sydney", "japan", "tokyo",
        "brazil", "mexico", "argentina", "philippines", "nigeria", "guatemala",
    ],
    # --- score ---
    "model": "claude-haiku-4-5",
    "score_concurrency": 5,
    "max_description_chars": 6000,
    "min_relevance": 6,            # shown when relevance >= this ...
    "min_fit": 4,                  # ... and fit >= this (4-5 is tagged 'stretch')
    "stretch_fit": 6,              # fit below this gets the 'stretch' tag
    "candidate": (
        "Computer science new grad (2026) who ships independently: three "
        "published Adobe Express add-ons with 4,500+ installs and $8,000 in "
        "competitive Adobe developer grants, plus multi-agent AI pipelines "
        "with VLM-based visual QA and GPU inference deployed to production. "
        "Two startup internships, including building and piloting an internal "
        "AI content pipeline at an Accel-backed fintech and running end-user "
        "demos. "
        "Targeting product engineer, founding engineer, forward deployed "
        "engineer, solutions engineer, applied AI engineer, developer "
        "relations, associate product manager, deployment strategist, and "
        "technical success roles at startups. "
        "Location: SF Bay Area on-site/hybrid, or US-remote. "
        "\n\n"
        "Decisive criterion: score on whether the person would be writing "
        "code and building most days. A customer-facing or non-SWE title "
        "with real engineering ownership scores high. The same title where "
        "the work is configuration, onboarding, training, account management, "
        "or running playbooks scores low, regardless of what it is called. "
        "'Forward Deployed Engineer' at a company that means implementation "
        "consultant is a low score."
    ),
}
