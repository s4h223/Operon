from datetime import date

from app.modules.text_analysis import (
    extract_traits,
    sentiment_compound,
    recency_weight_from_date,
    recency_weight_from_iso,
    term_code_to_date,
    recency_weight_from_term_code,
)


def test_sentiment_compound_positive_and_negative():
    assert sentiment_compound("This class was amazing and well organized!") > 0.3
    assert sentiment_compound("This class was a disaster and completely disorganized.") < -0.3


def test_extract_traits_detects_organized_with_positive_polarity():
    signals = extract_traits("Professor Simpkins is extremely well organized and clear in lectures.")
    trait_names = {s.trait for s in signals}
    assert "organized" in trait_names
    organized_signal = next(s for s in signals if s.trait == "organized")
    assert organized_signal.polarity > 0
    assert "organized" in organized_signal.evidence_span.lower()


def test_extract_traits_detects_disorganized_with_negative_polarity():
    signals = extract_traits("The class was disorganized and frustrating to follow.")
    organized_signal = next(s for s in signals if s.trait == "organized")
    assert organized_signal.polarity < 0


def test_extract_traits_detects_workload_traits():
    signals = extract_traits("Homework-heavy course but the workload was manageable overall.")
    trait_names = {s.trait for s in signals}
    assert "homework_heavy" in trait_names
    assert "manageable_workload" in trait_names


def test_extract_traits_no_matches_on_irrelevant_text():
    signals = extract_traits("I went to the store to buy groceries today.")
    assert signals == []


def test_recency_weight_decays_with_age():
    recent = recency_weight_from_date(date(2025, 1, 1), half_life_years=2.0, reference=date(2025, 6, 1))
    old = recency_weight_from_date(date(2015, 1, 1), half_life_years=2.0, reference=date(2025, 6, 1))
    assert recent > old
    assert 0.0 < old <= 1.0


def test_recency_weight_never_zero():
    ancient = recency_weight_from_date(date(1990, 1, 1), half_life_years=1.0, reference=date(2025, 1, 1))
    assert ancient > 0.0


def test_recency_weight_from_iso_handles_missing_date():
    assert recency_weight_from_iso(None) == 0.3
    assert recency_weight_from_iso("not-a-date") == 0.3


def test_term_code_to_date_parses_fall_spring():
    assert term_code_to_date("202508") == date(2025, 9, 1)
    assert term_code_to_date("202502") == date(2025, 2, 1)
    assert term_code_to_date("bogus") is None


def test_recency_weight_from_term_code_recent_beats_old():
    recent = recency_weight_from_term_code("202508", reference=date(2025, 12, 1))
    old = recency_weight_from_term_code("201508", reference=date(2025, 12, 1))
    assert recent > old
