"""Layers 10/11 QA: recency weighting and Bayesian/sample-size shrinkage,
beyond the unit-level coverage already in test_text_analysis.py and
test_scoring.py."""
from datetime import date

import pytest

from app.modules.scoring import GradeSignal, TraitObservation, score_grade_outcomes, score_teaching_experience, shrink_toward_prior
from app.modules.text_analysis import recency_weight_from_iso, recency_weight_from_term_code


# --- recency weighting edge cases -------------------------------------------

def test_current_semester_grade_data_gets_near_full_recency_weight():
    weight = recency_weight_from_term_code("202608", reference=date(2026, 9, 22))
    assert weight > 0.95


def test_five_year_old_grade_data_is_downweighted_but_not_zero():
    weight = recency_weight_from_term_code("202108", reference=date(2026, 9, 22))
    assert 0.0 < weight < 0.5


def test_web_discussion_decays_faster_than_grade_history_at_same_age():
    # Discussion half-life (1.5y) is shorter than grade half-life (3y), so
    # a 2-year-old comment should be weighted less than a 2-year-old
    # section at the same absolute age.
    two_years_ago_iso = "2024-09-22T00:00:00+00:00"
    discussion_weight = recency_weight_from_iso(two_years_ago_iso, reference=date(2026, 9, 22))
    grade_weight = recency_weight_from_term_code("202408", reference=date(2026, 9, 22))
    assert discussion_weight < grade_weight


def test_future_dated_term_code_does_not_produce_weight_above_one():
    # Defensive: a malformed/future term code shouldn't invert the decay
    # formula into a weight > 1.0.
    weight = recency_weight_from_term_code("203008", reference=date(2026, 9, 22))
    assert weight <= 1.0


# --- Bayesian/sample-size adjustment edge cases -----------------------------

def test_shrink_toward_prior_zero_sample_size_returns_prior_exactly():
    assert shrink_toward_prior(observed=1.0, sample_size=0, prior=0.42, k=10) == 0.42


def test_shrink_toward_prior_negative_sample_size_is_treated_like_zero():
    # Defensive: sample_size should never be negative in practice, but the
    # function should not do something bizarre (like a negative shrink
    # weight) if it ever is.
    assert shrink_toward_prior(observed=1.0, sample_size=-5, prior=0.42, k=10) == 0.42


def test_shrink_toward_prior_at_exactly_k_gives_half_weight():
    # By definition weight = n / (n + k); at n == k, weight is exactly 0.5.
    result = shrink_toward_prior(observed=1.0, sample_size=40, prior=0.0, k=40)
    assert result == pytest.approx(0.5)


def test_one_tiny_section_cannot_dominate_many_semesters_of_data_end_to_end():
    tiny_exceptional_section = GradeSignal(gpa=4.0, sample_size=2, recency_weight=1.0)
    many_semesters = [GradeSignal(gpa=3.0, sample_size=80, recency_weight=1.0) for _ in range(6)]

    combined = [tiny_exceptional_section] + many_semesters
    combined_result = score_grade_outcomes(combined)
    many_only_result = score_grade_outcomes(many_semesters)

    # Adding one tiny 2-student "perfect" section to 480 students of solid
    # 3.0 history should barely move the needle.
    assert abs(combined_result.raw_score - many_only_result.raw_score) < 0.02


def test_two_positive_comments_cannot_outweigh_years_of_teaching_discussion():
    years_of_consistent_signal = [TraitObservation("organized", 0.6, 0.9, True) for _ in range(30)]
    two_new_glowing_comments = [TraitObservation("organized", 1.0, 1.0, True) for _ in range(2)]

    established = score_teaching_experience(years_of_consistent_signal)
    with_new_comments = score_teaching_experience(years_of_consistent_signal + two_new_glowing_comments)

    # Two comments among 32 should nudge, not transform, the score.
    assert with_new_comments.raw_score - established.raw_score < 0.05
