# FYVE

FYVE is a Georgia Tech-only professor recommendation engine. It answers one
question: **given this exact GT course, the professors actually teaching it
this semester, and how this specific student wants to learn, who is the
best-fit professor for them?** Not "who has the highest rating" — best fit
for *this* student.

No OpenAI/Claude/Gemini, no paid search or data APIs, no API keys anywhere
in the pipeline. Recommendations are built from public GT schedule/grade
data, best-effort public syllabus text, public teaching-recognition
mentions, and a modular public-web/Reddit research pass, combined with
local deterministic NLP (VADER sentiment + a controlled trait vocabulary).

## Stack

- **Frontend**: Next.js 16 (App Router) + TypeScript, in `frontend/`.
- **Backend**: Python + FastAPI, in `backend/`.
- **Storage**: SQLite (`backend/data/fyve.sqlite3`), used both as the
  structured-fact store and as the HTTP response cache.
- **NLP**: VADER (local, rule-based sentiment) + keyword/phrase trait
  extraction. No LLM calls anywhere in the recommendation path.

## Repository layout

```
backend/
  app/
    config.py            # TTLs, base URLs, user agent
    db.py                 # SQLite schema (every fact keeps source_url + retrieved_at)
    modules/
      normalization.py    # professor-name & course-code canonicalization
      cache.py             # TTL'd HTTP response cache
      schedule.py          # GT Oscar dynamic schedule search (public, unauthenticated)
      grades.py             # Course Critique grade distributions (never automates GT CAS login)
      syllabus.py            # generic syllabus text -> structured facts
      teaching_recognition.py # public GT teaching-award/recognition mentions
      web_discovery.py        # pluggable WebSource protocol + DuckDuckGo HTML source
      reddit_ingest.py         # Reddit's public, unauthenticated .json search API
      text_analysis.py          # VADER sentiment, trait vocabulary, recency weighting
      scoring.py                 # 7 normalized fit components + Bayesian shrinkage
      confidence.py                # separate Data Confidence score
      explanations.py               # evidence-grounded reasons/tradeoffs
      recommendation.py              # selects exactly one Best Match + alternatives
      comparison.py                   # side-by-side professor comparison
      pipeline.py                      # orchestrates all of the above per course/term
    api/routes.py                       # FastAPI endpoints
    data/course_catalog.py               # seed course list for search/autocomplete
  tests/                                  # 80 tests, mocked HTTP (respx), no live network needed

frontend/
  app/                     # guided flow: semester -> course -> scope -> questions -> results
  components/               # QuestionStep, ResultsView, ComparisonView, Logo
  lib/                        # typed API client

legacy-sat-desmos-tutor/       # unrelated prior scaffold in this repo, moved aside (not deleted)
```

## Running it

### Backend

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_BASE=http://localhost:8000
npm run dev
```

### Tests

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

All 80 backend tests pass without any live network access - every external
call is mocked (`respx`) against fixtures shaped like the real pages
(Oscar's dynamic schedule HTML, Course Critique JSON, DuckDuckGo HTML
results, Reddit's `.json` search response).

## A known limitation of *this* sandbox, not of the code

This development session's network egress policy blocks the actual GT,
DuckDuckGo, and Reddit hosts (confirmed via the proxy status: `403 policy
denial` on `registration.gatech.edu`, etc.) - so live scraping could not be
demonstrated end-to-end from here. The scraping/parsing code is real and
targets the real public endpoints (GT's Oscar dynamic schedule search,
Course Critique's course API, DuckDuckGo's keyless HTML results, Reddit's
keyless `.json` search); it is exercised end-to-end in
`tests/test_pipeline_integration.py` against mocked responses shaped like
the real ones. Running the backend on a machine with normal internet
access should let it fetch live data - GT site markup can of course still
drift over time, which is exactly why every source degrades to
`status: "unavailable"` instead of guessing when a fetch or parse fails.

## Principles this codebase enforces in code, not just in the spec

- **Never automate a GT login.** `grades.py` makes one unauthenticated
  request to Course Critique; the moment the response redirects toward
  `login.gatech.edu`/CAS, it stops and reports the data unavailable.
- **Never invent a missing fact.** Every scraper returns
  `status: "unavailable"` (with a human-readable reason) on failure, never
  a fabricated number. `scoring.py` never scores a missing component as
  zero - it's excluded and its weight is redistributed across the
  components that do have evidence, and Data Confidence drops accordingly.
- **Course-specific evidence before professor-wide evidence.** The scoring
  layer only ever receives course-specific grade rows and course/professor
  co-mentioned discussion; professor-wide-only signals are not mixed in.
- **Recent over old.** `text_analysis.recency_weight_from_iso` /
  `recency_weight_from_term_code` exponentially decay older evidence
  (discussion half-life ~1.5y, grade-history half-life ~3y), never to zero.
- **Sample-size correction.** `scoring.shrink_toward_prior` pulls small
  samples toward a neutral prior (Bayesian-shrinkage style) so one
  exceptional 3-student section or two comments can't outweigh years of
  stable data - verified in `tests/test_scoring.py`.
- **Only ask a preference question if it could change the answer.**
  `pipeline.relevant_questions` probes the gathered evidence for each
  candidate professor and only surfaces a question (workload, assessment
  style, structure, attendance, support, modality) if at least one
  professor has evidence that question could actually move.
- **Every reason is traceable to stored evidence.** `explanations.py`
  builds reasons/tradeoffs only from each component's own evidence note
  (and, where available, the real sentence it came from) - never free text.

## Vertical slice status

The full pipeline (schedule → grades → syllabus discovery → web/Reddit
research → trait extraction → scoring → recommendation → comparison) is
wired end-to-end and demonstrated for **CS 1301** in
`tests/test_pipeline_integration.py`. Nothing in the pipeline is
CS-1301-specific: `app/data/course_catalog.py` is a small seed list for
autocomplete (it includes every course the product spec names - CS 1301,
MATH 1552, ACCT 2101, ISYE 2027 - plus a few more), but any valid
`SUBJECT NUMBER` typed by the user flows through the exact same live
retrieval path even if it's not in that seed list. Generalizing "for real"
mostly means growing that seed catalog (or replacing it with a scraped
catalog crawl) and letting the GT site structure prove itself out against
more courses.

## What isn't built yet

- The sentence-transformers-based semantic clustering the spec calls out
  as optional is not wired in; `text_analysis.py` is structured so it can
  be added as an additional signal without touching its callers.
- Syllabus discovery currently reuses whatever web-discovery results
  mention "syllabus" in the title/snippet rather than a dedicated crawl of
  GT department syllabus pages - a reasonable place to add a dedicated
  syllabus-source module later.
