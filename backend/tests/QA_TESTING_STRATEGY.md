# FYVE Backend — QA Testing Strategy

## Scope and approach

Every layer is tested **in isolation** first (pure functions / mocked HTTP,
no live network), then the full pipeline is exercised end-to-end with
realistic fixtures for CS 1301, MATH 1552, PHYS 2211, and ACCT 2101.
No test depends on live GT/DuckDuckGo/Reddit access — everything goes
through `respx` HTTP mocks or plain fixture data.

## Layer → test file map

| # | Layer | Test file(s) |
|---|-------|--------------|
| 1 | Data ingestion (network/cache behavior) | `test_edge_cases_ingestion.py`, `test_pipeline_integration.py` |
| 2 | OSCAR parsing | `test_schedule.py`, `test_edge_cases_parsing.py` |
| 3 | Course Critique parsing | `test_grades.py`, `test_edge_cases_parsing.py` |
| 4 | Syllabus parsing | `test_syllabus.py`, `test_edge_cases_parsing.py` |
| 5 | Professor-name normalization | `test_normalization.py`, `test_normalization_edge_cases.py` |
| 6 | Course-code normalization | `test_normalization.py`, `test_normalization_edge_cases.py` |
| 7 | Public-web discussion parsing | `test_web_discovery.py`, `test_discussion_analysis.py` |
| 8 | Duplicate discussion detection | `test_web_discovery.py`, `test_discussion_analysis.py` |
| 9 | Historical grade calculations | `test_grade_calculations.py` |
| 10 | Recency weighting | `test_text_analysis.py`, `test_recency_and_shrinkage.py` |
| 11 | Bayesian/sample-size adjustment | `test_scoring.py`, `test_recency_and_shrinkage.py` |
| 12 | Missing-data handling | `test_scoring.py`, `test_missing_data_invariants.py` |
| 13 | User preference weight generation | `test_scoring.py`, `test_preference_weights.py` |
| 14 | Personalized professor scoring | `test_scoring.py`, `test_scoring_determinism.py` |
| 15 | Confidence scoring | `test_confidence.py` |
| 16 | Explanation generation | `test_explanations.py` |
| 17 | Professor comparison | `test_comparison.py` |
| 18 | Full end-to-end recommendation flow | `test_pipeline_integration.py`, `test_synthetic_invariants.py` |
| — | Source provenance on every displayed stat | `test_source_provenance.py` |

## Fixtures

`tests/fixtures/` holds realistic per-course HTML/JSON:
- `oscar_cs1301_sample.html` (existing) — CS 1301, 2 professors.
- `oscar_math1552_sample.html` — MATH 1552, 3 professors, one teaching two sections.
- `oscar_phys2211_sample.html` — PHYS 2211, 1 professor only (tests the
  "only one available professor" case).
- `oscar_acct2101_sample.html` — ACCT 2101, used for a professor with a
  single historical section vs. one with many.
- `oscar_malformed_structure.html` — deliberately different table markup
  (simulates a GT site redesign) to prove parsing degrades to "unavailable"
  rather than crashing or hallucinating instructors.
- Grade/syllabus/web/Reddit payloads are built inline in each test module
  (small enough that inline Python dicts are more readable than extra files).

## Edge cases covered (mapped to where)

- Professor with one historical section → `test_grade_calculations.py`
- Professor with many historical sections → `test_grade_calculations.py`
- Professor with no syllabus → `test_scoring.py` (`assessment_fit=None`), `test_pipeline_integration.py`
- Professor with no grade history → `test_grade_calculations.py`, `test_missing_data_invariants.py`
- Professor with no online discussion → `test_missing_data_invariants.py`
- Conflicting online opinions → `test_discussion_analysis.py`
- Duplicate Reddit/forum posts → `test_web_discovery.py`, `test_discussion_analysis.py`
- Professor name variations → `test_normalization_edge_cases.py`
- Malformed syllabus → `test_edge_cases_parsing.py`
- Missing grading percentages → `test_edge_cases_parsing.py`
- Current professor with no historical data → `test_pipeline_integration.py`
- Historical professor not teaching current semester → `test_pipeline_integration.py` (documents current behavior: such a professor is never surfaced — see Known Limitations)
- One professor teaching multiple sections → `test_schedule.py`, `test_grade_calculations.py`
- Course with only one available professor → `test_edge_cases_parsing.py`, `test_pipeline_integration.py`
- Website timeout → `test_edge_cases_ingestion.py`
- HTTP error → `test_edge_cases_ingestion.py`
- Changed HTML structure → `test_edge_cases_parsing.py`
- Empty search result → `test_edge_cases_ingestion.py`
- Partial source outage (one source down, others fine) → `test_edge_cases_ingestion.py`
- Stale cached data → `test_edge_cases_ingestion.py`

## Invariants asserted (synthetic profiles, `test_synthetic_invariants.py` + others)

- Recommendations are deterministic (same input → same output, run twice).
- Dynamic weights always sum to 1.0 (exhaustively over every non-empty
  subset of the 7 components × all 4 priority values).
- Missing data is never treated as zero (component excluded, not scored 0).
- Unavailable components' weight is redistributed proportionally.
- Sparse data lowers Data Confidence relative to rich data at the same fit.
- One tiny sample cannot dominate many semesters (shrinkage).
- Course-specific data is the *only* grade data ever fed into scoring
  (there is currently no professor-wide-across-other-courses channel —
  see Known Limitations).
- Recent data outweighs very old data (recency-weighted averaging).
- Changing user preferences can flip the recommended professor.
- The recommended professor is always drawn from the current term's
  schedule sections (there is no historical-professor mode yet — see
  Known Limitations).
- Explanations/tradeoffs are grounded in real `ComponentScore.note` text.
- Every displayed statistic (course GPA, syllabus %, component score)
  carries a `source_url`.

## Adversarial review findings

Manual review beyond the automated suite, looking specifically for logic
bugs that pass individual unit tests but misbehave in combination.

### Fixed (confirmed via a failing test first, then a minimal patch)

1. **`assessment_fit` inflated a partially-extracted syllabus to 100%.**
   `exam_share = exam / (exam+hw+proj)` used the sum of only the categories
   the extractor *found* as the denominator. A syllabus page yielding only
   "Exams: 40%" (homework/project genuinely unmentioned, not 0%) scored as
   if exams were the entire grade (`exam_share = 1.0`). Fixed by
   normalizing against `max(total_extracted, 100.0)` instead.
   Test: `test_synthetic_invariants.py::test_assessment_fit_partial_syllabus_extraction_does_not_claim_100_percent`.

2. **`structure_fit` silently defaulted a missing preference-dimension to
   neutral (0.5) instead of excluding it.** When a student asked about
   attendance but there was zero attendance evidence (no trait mentions,
   no syllabus attendance policy), the function fell through to an
   `else: required = 0.5` default and still returned a non-None score with
   nonzero confidence - meaning the function's own
   `if not parts: return None` safety net could never actually fire.
   Fixed by only appending to `parts` when real evidence backs that
   dimension. Test: `test_synthetic_invariants.py::test_structure_fit_returns_none_when_only_requested_dimension_has_zero_evidence`.

3. **Source provenance was dropped at the pipeline boundary.** `GradeRow`
   and `SyllabusFacts` (the raw scraped facts) always carried `source_url`,
   but `GradeSignal`/`SyllabusSignal`/`TraitObservation` (what `scoring.py`
   actually consumes) did not, so no source ever reached the API response
   - a displayed Personal Fit or comparison-row GPA had no way to be
   traced back to where it came from, contradicting the product spec
   ("every stored fact must retain its source URL"). Fixed by adding
   `source_url` to those three dataclasses, threading it through
   `pipeline.py`, and adding a `sources: list[str]` field to
   `ComponentScore` (exposed in the `/api/recommend` response) and
   `grade_sources` to `ComparisonRow` (exposed in `/api/compare`).
   Tests: `test_source_provenance.py` (4 tests).

4. **Workload-trait direction ignored negation for sentiment-neutral
   keywords.** "homework heavy", "attendance heavy" etc. are factual
   phrases VADER has no sentiment opinion on (compound stays `0.0`)
   regardless of surrounding negation, but `_workload_intensity`'s
   direction is inferred purely from *which* keyword matched, with a
   magnitude fallback of `0.3` when polarity is exactly `0.0`. A student
   writing "not homework heavy" (i.e. explicitly saying the workload is
   light) was scored as pushing the workload estimate *heavier* -
   backwards. Fixed narrowly in `text_analysis.extract_traits`: when a
   negation cue (not/n't/never/hardly/no longer) appears shortly before a
   matched keyword *and* VADER found no sentiment for the sentence, the
   signal is skipped rather than emitted in a guessed direction - this
   only ever suppresses a signal, it never invents one. Verified it
   doesn't suppress keyword phrases that legitimately contain "not"
   themselves (e.g. "not too much work"). Tests:
   `test_discussion_analysis.py::test_negated_neutral_keyword_does_not_emit_backwards_signal`
   and `::test_negation_does_not_suppress_keywords_that_already_contain_not`.

   This is a narrow mitigation, not a general negation-detection system -
   it converts "wrong direction" into "no signal" for the one failure mode
   found, not into a correct positive-direction read. Full negation-scope
   understanding across all 15 traits would be a genuine NLP feature
   addition (and arguably in tension with the spec's "avoid requiring an
   LLM" instruction, which is why the deterministic keyword approach was
   chosen in the first place) - out of scope for this QA pass.

### Documented, not fixed (real risks, but fixing them is a feature
addition or would require data GT's public pages don't expose)

5. **Same-name collision can merge two different professors.**
   `professor_key()` is `first_last` derived only from the name string on
   the public schedule page. Georgia Tech has no public per-instructor ID
   in the schedule data to disambiguate two different people who happen to
   share a first+last name (a real, if infrequent, possibility at a large
   university). If it happened, their grade/discussion evidence would be
   silently pooled into one profile. There is no way to fix this from
   public data alone; flagging it as a known data-integrity risk rather
   than papering over it with false confidence.

6. **A professor's `modality` and `section_meta` (schedule) reflect only
   their *first* listed section, not all of them.** A professor teaching
   one in-person and one online section of the same course has their
   `schedule_modality_fit` scored against whichever section happened to
   sort first in the Oscar page. The per-section detail is still available
   unaggregated via `/api/courses/{subject}/{course}/professors`, so
   nothing is hidden from the user, but the single aggregate score is a
   simplification. Worth a follow-up (e.g. "best matching section" instead
   of "first section") if mixed-modality instructors turn out to be common
   in practice.

7. **Frontend TypeScript types don't yet surface the new `sources` /
   `grade_sources` fields** added by fix #3. The API returns them; the
   Next.js UI doesn't render them yet. Not a correctness bug (extra JSON
   fields are simply unused), but worth a follow-up so the "every stat has
   a source" guarantee is visible to an actual user, not just to the API
   response.

## Known limitations surfaced by this QA pass (documented, not silently ignored)

1. **No professor-wide-history channel.** The product spec asks for
   course-specific evidence to "heavily prioritize" over overall teaching
   history, implying overall history is also gathered as a secondary
   signal. Today only course-specific grade/discussion evidence is ever
   fetched — there is no fallback "how has this professor done in general"
   signal. This is architecturally clean (course-specific evidence can
   never be diluted by off-course data) but narrower than the spec's
   language. Flagged in the adversarial review; not implemented here since
   it is a feature addition, not a bug fix.
2. **No historical-professor mode.** "Unless the user explicitly requests
   historical professors" implies such a request path exists; it does not.
   `pipeline.gather_profiles` only ever considers professors in the
   selected term's live schedule. This is the *safer* default (never
   recommends someone not currently teaching the course) but the opt-in
   historical path is unbuilt.
