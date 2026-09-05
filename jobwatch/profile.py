"""Every threshold and list the pipeline uses. Edit this file, nothing else."""
from __future__ import annotations

PROFILE = {
    # --- HTTP ---
    "probe_rps_per_host": 3.0,     # shared per-hostname ceiling, all workers
    "workers": 12,                 # in-flight requests; more just holds more bodies in RAM at 3 rps/host
    "http_retries": 3,
    # --- verify ---
    "dead_slug_days": 30,          # skip re-probing a dead slug for this long
    # --- diff ---
    "max_posting_age_days": 14,    # older postings are 'stale', never scored
    "prune_days": 90,
    "timezone": "America/Los_Angeles",
    # --- prefilter ---
    "max_years": 3,
    "level_terms": [
        "senior", "sr", "staff", "principal", "director", "head of", "vp",
        "lead", "manager", "intern", "internship", "distinguished", "fellow",
        "chief", "ii", "iii", "iv", "l4", "l5", "l6", "l7", "l8",
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
        "south san francisco", "foster city", "burlingame",
    ],
    "non_us_terms": [
        "uk", "united kingdom", "london", "europe", "emea", "apac", "canada",
        "toronto", "vancouver", "india", "bangalore", "bengaluru", "latam",
        "germany", "berlin", "france", "paris", "netherlands", "amsterdam",
        "ireland", "dublin", "spain", "portugal", "poland", "israel",
        "tel aviv", "singapore", "australia", "sydney", "japan", "tokyo",
        "brazil", "mexico", "argentina", "philippines", "nigeria",
    ],
    # --- score ---
    "model": "claude-haiku-4-5",
    "score_concurrency": 5,
    "max_description_chars": 6000,
    "min_score": 6,
    "candidate": (
        "Computer science new grad (graduating 2026) with two startup "
        "engineering internships. Targeting product engineer, founding "
        "engineer, forward deployed engineer (FDE), solutions engineer, "
        "applied AI, and similar builder roles at well-funded startups. "
        "Location: San Francisco Bay Area on-site/hybrid, or US-remote."
    ),
}
