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
# NOTE on this URL's history: "registration.gatech.edu" (the original guess)
# doesn't exist (GT's own DNS returns NXDOMAIN). "oscar.gatech.edu/pls/bprod/
# bwckschd.p_get_crse_unsec" (the next guess, based on an older open-source
# scraper) is real but now rejected by GT's Oracle ORDS gateway with
# NotAuthorizedOrNotFound - GT has since migrated its live public schedule
# search to the modern Banner 9 Self-Service REST API on a *different* host,
# confirmed against the current source of github.com/gt-scheduler/crawler-v2
# (the actively maintained successor to the crawler that used the old path).
# No login is required for this either - the crawler-v2 project scrapes it
# unauthenticated; it just needs an anonymous session cookie established via
# a GET before the search requests, not a GT account.
GT_SCHEDULE_BASE = "https://registration.banner.gatech.edu/StudentRegistrationSsb"

# NOTE on this URL's history: "critique.gatech.edu/api/course/{subject}/
# {course}" (the original guess) doesn't exist - critique.gatech.edu is a
# client-rendered React app with no such REST path of its own. The actual
# data it displays comes from a separate, public, unauthenticated AWS API
# Gateway endpoint (no GT login of any kind - confirmed by fetching it
# directly with no cookies/auth and getting full grade data back), verified
# against the current source of the actively maintained github.com/
# gt-scheduler/firebase-conf (its `course_critique_cache.ts` cache proxy)
# and github.com/gt-scheduler/website (its `Course.ts` GPA-fetch bean).
# Query with `?courseID=SUBJ NUMBER` (e.g. "CS 1301", space included, URL
# encoded). Response shape: {"header": [...], "raw": [per-historical-section
# records]} - NOT a bare list, and field names are "Term"/"GPA"/
# "instructor_name"/"class_size_group" (title-cased in a couple of spots),
# not the lowercase "term"/"gpa" guessed originally.
COURSE_CRITIQUE_BASE = "https://c4citk6s9k.execute-api.us-east-1.amazonaws.com/prod/data/course"
DUCKDUCKGO_HTML_BASE = "https://html.duckduckgo.com/html/"
REDDIT_SEARCH_BASE = "https://www.reddit.com/r/gatech/search.json"

REQUEST_DELAY_SECONDS = float(os.environ.get("FYVE_REQUEST_DELAY", "1.0"))
