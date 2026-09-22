"""Layer 9 QA: historical grade calculations - GPA-from-counts math,
recency-weighted averaging across sections, and the one-section vs.
many-section professor edge cases, using realistic numbers for CS 1301,
MATH 1552, PHYS 2211, and ACCT 2101."""
import json

import pytest

from app.modules.grades import _gpa_from_counts, _parse_records, rows_for_professor
from app.modules.scoring import GradeSignal, score_grade_outcomes


# --- GPA-from-counts arithmetic ---------------------------------------------

def test_gpa_from_counts_all_a():
    assert _gpa_from_counts({"a": 50, "b": 0, "c": 0, "d": 0, "f": 0, "w": 0}) == 4.0


def test_gpa_from_counts_all_f():
    assert _gpa_from_counts({"a": 0, "b": 0, "c": 0, "d": 0, "f": 50, "w": 0}) == 0.0


def test_gpa_from_counts_withdrawals_excluded_from_gpa_denominator():
    # 10 W's should not drag the GPA down - W is not a graded outcome.
    with_w = _gpa_from_counts({"a": 20, "b": 0, "c": 0, "d": 0, "f": 0, "w": 10})
    without_w = _gpa_from_counts({"a": 20, "b": 0, "c": 0, "d": 0, "f": 0, "w": 0})
    assert with_w == without_w == 4.0


def test_gpa_from_counts_all_withdrawn_returns_none_not_zero():
    # Missing/undefined GPA (nobody was actually graded) must not silently
    # become 0.0, which would look like a class full of F's.
    assert _gpa_from_counts({"a": 0, "b": 0, "c": 0, "d": 0, "f": 0, "w": 30}) is None


def test_gpa_from_counts_realistic_phys2211_distribution():
    # ~typical intro physics distribution
    counts = {"a": 45, "b": 60, "c": 40, "d": 15, "f": 10, "w": 12}
    gpa = _gpa_from_counts(counts)
    assert 2.2 < gpa < 3.0


# --- one-section vs many-section professor -----------------------------------

def test_professor_with_one_historical_section():
    records = {
        "raw": [
            {
                "instructor_name": "Patel, Anjali R", "Term": "Fall 2024",
                "class_size_group": "Mid-Size (21-30 students)",
                "GPA": 3.1, "A": 40, "B": 30, "C": 16, "D": 4, "F": 2, "W": 8,
            },
        ]
    }
    rows = _parse_records(json.dumps(records), "PHYS", "2211", "http://critique.test/phys2211")
    prof_rows = rows_for_professor(rows, "anjali_patel")
    assert len(prof_rows) == 1
    assert prof_rows[0].sample_size == 25  # "Mid-Size (21-30 students)" bucket estimate


def test_professor_with_many_historical_sections():
    seasons = ["Fall 2020", "Fall 2021", "Fall 2022", "Fall 2023", "Fall 2024", "Fall 2025"]
    records = {
        "raw": [
            {
                "instructor_name": "Chen, Wei L", "Term": season,
                "class_size_group": "Large (31-49 students)",
                "GPA": 3.2, "A": 43, "B": 29, "C": 14, "D": 4, "F": 3, "W": 7,
            }
            for season in seasons
        ]
    }
    rows = _parse_records(json.dumps(records), "MATH", "1552", "http://critique.test/math1552")
    prof_rows = rows_for_professor(rows, "wei_chen")
    assert len(prof_rows) == 6
    assert sum(r.sample_size for r in prof_rows) == 240  # 6 sections x 40 (Large bucket estimate)


def test_many_sections_yield_higher_confidence_than_one_section_same_gpa():
    one_section = [GradeSignal(gpa=3.2, sample_size=70, recency_weight=1.0)]
    many_sections = [GradeSignal(gpa=3.2, sample_size=70, recency_weight=w) for w in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]]
    one = score_grade_outcomes(one_section)
    many = score_grade_outcomes(many_sections)
    assert many.confidence > one.confidence
    assert many.sample_size == 420


# --- recency-weighted averaging across sections (recent > old) --------------

def test_recency_weighted_average_leans_toward_recent_semester():
    old_strong = GradeSignal(gpa=3.9, sample_size=100, recency_weight=0.1)
    recent_weak = GradeSignal(gpa=2.2, sample_size=100, recency_weight=1.0)
    result = score_grade_outcomes([old_strong, recent_weak])
    # A naive unweighted average of 3.9 and 2.2 is 3.05/4=0.7625 (pre-shrink).
    # The recency-weighted observed value should sit well below that,
    # closer to the recent (weak) semester.
    naive_unweighted = ((3.9 + 2.2) / 2) / 4.0
    assert result.raw_score < naive_unweighted


def test_equal_recency_weights_produce_plain_sample_weighted_average():
    a = GradeSignal(gpa=4.0, sample_size=100, recency_weight=1.0)
    b = GradeSignal(gpa=2.0, sample_size=100, recency_weight=1.0)
    result = score_grade_outcomes([a, b])
    # With equal weights and equal sample sizes, the pre-shrink observed
    # value is exactly the midpoint (3.0/4=0.75); after shrink toward the
    # 0.75 prior with n=200, it should land very close to that midpoint.
    assert 0.7 < result.raw_score < 0.8


# --- realistic multi-course sanity checks -----------------------------------

@pytest.mark.parametrize(
    "subject,course_number,gpa,n",
    [
        ("CS", "1301", 3.4, 180),
        ("MATH", "1552", 2.9, 220),
        ("PHYS", "2211", 2.7, 150),
        ("ACCT", "2101", 3.3, 90),
    ],
)
def test_realistic_course_grade_signal_scores_in_sane_range(subject, course_number, gpa, n):
    result = score_grade_outcomes([GradeSignal(gpa=gpa, sample_size=n, recency_weight=1.0)])
    assert result.raw_score is not None
    assert 0.0 <= result.raw_score <= 1.0
    assert result.sample_size == n
