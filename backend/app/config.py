"""Central configuration for the FYVE backend.

FYVE (formerly prototyped as "Operon") is a Georgia Tech-only professor
recommendation engine. Nothing here talks to a paid API or requires a key -
every external call is to a public page, a public unauthenticated JSON
endpoint, or a local model.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "FYVE"

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = os.environ.get("FYVE_DB_PATH", str(DATA_DIR / "fyve.sqlite3"))

HTTP_TIMEOUT_SECONDS = float(os.environ.get("FYVE_HTTP_TIMEOUT", "15"))
HTTP_USER_AGENT = os.environ.get(
    "FYVE_USER_AGENT",
    "FYVE-research-bot/0.1 (Georgia Tech course-fit research tool; "
    "contact: sahilgohel75@gmail.com; respects robots.txt)",
)

# Cache TTLs, in seconds, per source type. Structured historical data (grades,
# syllabi) changes rarely and is cached long. Current-semester schedule data
# and online discussion should be refreshed more often.
CACHE_TTL_SECONDS = {
    "schedule": 60 * 60 * 12,       # 12 hours - current-term section data
    "grades": 60 * 60 * 24 * 30,    # 30 days - historical grade distributions
    "syllabus": 60 * 60 * 24 * 30,  # 30 days - syllabi rarely change mid-term
    "recognition": 60 * 60 * 24 * 14,
    "web": 60 * 60 * 24 * 3,        # 3 days - forum/discussion content
    "reddit": 60 * 60 * 24 * 3,
}

# Sites Operon/FYVE is permitted to touch. Anything not in this allowlist of
# *kinds* of sources should not be added without reviewing robots.txt and
# terms of service first. No GT authenticated system is ever touched.
#
# NOTE: "registration.gatech.edu" (the original guess here) does not exist -
# confirmed by GT's own DNS returning NXDOMAIN for it. The real, public,
# unauthenticated host for GT's Banner "Oscar" system is oscar.gatech.edu;
# independent open-source projects (e.g. github.com/gt-scheduler/crawler,
# github.com/chris-martin/grouch) have scraped bwckschd.p_get_crse_unsec on
# this host without any login for years, which is what "_unsec" (unsecured)
# signals about the endpoint itself.
GT_SCHEDULE_BASE = "https://oscar.gatech.edu/pls/bprod"
COURSE_CRITIQUE_BASE = "https://critique.gatech.edu"
DUCKDUCKGO_HTML_BASE = "https://html.duckduckgo.com/html/"
REDDIT_SEARCH_BASE = "https://www.reddit.com/r/gatech/search.json"

REQUEST_DELAY_SECONDS = float(os.environ.get("FYVE_REQUEST_DELAY", "1.0"))
