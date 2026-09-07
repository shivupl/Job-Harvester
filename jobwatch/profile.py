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
    "max_years": None,             # None disables the years prefilter; the model reads the body
    "level_terms": [
        "senior", "sr", "principal", "director", "head of", "vp",
        "distinguished", "chief", "intern", "internship",
        "ii", "iii", "iv", "l4", "l5", "l6", "l7", "l8",
        # phrases replacing bare "manager" and "lead"
        "engineering manager", "general manager", "group manager",
        "senior manager",
        "tech lead", "team lead", "technical lead", "engineering lead",
        # "staff" is handled separately in prefilter.py: it must not match
        # "Member of Technical Staff", which is used at every level.
    ],
    # Skips the level check only. Function, location, years still apply,
    # so "Associate Counsel" and "Associate Recruiter" stay dropped.
    "early_career_bypass": [
        "associate", "new grad", "new graduate", "entry level", "entry-level",
        "early career", "early-career", "university", "graduate", "college grad",
        "junior", "rotational", "cohort", "apprentice",
    ],
    # Never bypassed, even by an early-career term in the same title.
    "hard_level_terms": ["intern", "internship"],
    "function_terms": [
        "recruiter", "recruiting", "account executive", "accounting",
        "legal", "counsel", "paralegal", "hr", "designer", "nurse",
        "physician", "clinician", "therapist", "payroll",
        "executive assistant", "office manager",
    ],
    # A title with any of these skips the function check: "Marketing Engineer"
    # is an engineer. Level, location, and years still apply.
    "builder_bypass": ["engineer", "engineering", "developer", "programmer", "software", "scientist"],
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
    "us_terms": ["united states", "usa", "u.s.", "u.s.a", "us"],
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
        "chile", "colombia", "costa rica", "latin america", "switzerland",
        "new zealand", "nz", "calgary", "montreal", "ottawa", "munich",
        "bavaria", "sweden", "stockholm", "denmark", "copenhagen", "norway",
        "finland", "italy", "milan", "austria", "vienna", "belgium",
        "czech", "prague", "hungary", "romania", "ukraine", "turkey",
        "uae", "dubai", "saudi", "egypt", "south africa", "kenya", "pakistan",
        "vietnam", "thailand", "indonesia", "malaysia", "korea", "seoul",
        "taiwan", "hong kong", "china", "shanghai", "beijing",
    ],
    # --- score ---
    "provider": "openai",          # "openai" or "anthropic"; key from OPENAI_API_KEY / ANTHROPIC_API_KEY
    "model": "gpt-5.6-luna",       # anthropic alternative: "claude-haiku-4-5"
    "reasoning_effort": "low",     # openai reasoning models only; ignored by anthropic
    "max_completion_tokens": 2000, # openai: reasoning tokens count against this
    "score_concurrency": 5,
    "max_description_chars": None, # None sends the whole description; requirements often sit at the end
    "min_relevance": 6,            # shown when relevance >= this ...
    "min_fit": 4,                  # ... and fit >= this (4-5 is tagged 'stretch')
    "stretch_fit": 6,              # fit below this gets the 'stretch' tag
    "hide_location_fits": ["non_us"],   # model-tagged location fits never shown
    "board_days": 30,              # board.html shows eligible postings first seen within this window
    "candidate": (
        "Computer science graduate (June 2026), available to start "
        "immediately, who ships independently: three "
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
