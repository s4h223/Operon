"""Layers 7/8 QA: public-web discussion parsing + duplicate detection,
including conflicting opinions and duplicate posts across sources."""
from app.modules.scoring import TraitObservation, score_teaching_experience
from app.modules.text_analysis import extract_traits
from app.modules.web_discovery import WebResult, dedupe_results, tag_relevance


def _r(url, title, snippet, source="web"):
    return WebResult(url=url, title=title, snippet=snippet, source=source, domain="example.test")


# --- conflicting online opinions --------------------------------------------

def test_conflicting_opinions_extract_both_polarities_from_same_professor():
    positive = extract_traits("Charles Simpkins is extremely well organized and clear.")
    negative = extract_traits("Charles Simpkins was disorganized and confusing all semester.")
    pos_signal = next(s for s in positive if s.trait == "organized")
    neg_signal = next(s for s in negative if s.trait == "organized")
    assert pos_signal.polarity > 0
    assert neg_signal.polarity < 0


def test_conflicting_opinions_net_toward_neutral_in_teaching_experience_score():
    observations = [
        TraitObservation("organized", polarity=0.85, recency_weight=1.0, mentions_both=True),
        TraitObservation("organized", polarity=-0.85, recency_weight=1.0, mentions_both=True),
    ]
    result = score_teaching_experience(observations)
    assert result.raw_score is not None
    # Equal and opposite signals of equal weight should net close to the
    # neutral prior (0.5), not swing strongly either way.
    assert 0.4 <= result.raw_score <= 0.6
    assert result.sample_size == 2


def test_conflicting_opinions_do_not_cancel_out_sample_size():
    # Even though the polarities cancel, both comments are still real
    # evidence and should count toward sample_size/confidence - conflicting
    # opinions are not the same as "no opinion".
    observations = [
        TraitObservation("organized", polarity=0.9, recency_weight=1.0, mentions_both=True),
        TraitObservation("organized", polarity=-0.9, recency_weight=1.0, mentions_both=True),
        TraitObservation("organized", polarity=0.9, recency_weight=1.0, mentions_both=True),
        TraitObservation("organized", polarity=-0.9, recency_weight=1.0, mentions_both=True),
    ]
    conflicting = score_teaching_experience(observations)
    single_opinion = score_teaching_experience(observations[:1])
    assert conflicting.sample_size > single_opinion.sample_size
    assert conflicting.confidence > single_opinion.confidence


def test_multiple_independent_comments_strengthen_same_direction_signal():
    # The spec: "multiple independent comments expressing the same idea
    # should strengthen a signal" - more independently-worded positive
    # mentions should shrink less toward the neutral prior.
    few = [TraitObservation("organized", 0.7, 1.0, True)]
    many = [TraitObservation("organized", 0.7, 1.0, True) for _ in range(10)]
    few_score = score_teaching_experience(few).raw_score
    many_score = score_teaching_experience(many).raw_score
    assert many_score > few_score


# --- duplicate discussion detection -----------------------------------------

def test_duplicate_reddit_crosspost_different_url_same_text_deduped():
    results = [
        _r("https://www.reddit.com/r/gatech/comments/abc/x/", "CS 1301 review", "Simpkins is great, very organized", source="reddit"),
        _r("https://old.reddit.com/r/gatech/comments/abc/x/", "CS 1301 review", "Simpkins is great, very organized", source="reddit"),
    ]
    deduped = dedupe_results(results)
    assert len(deduped) == 1


def test_duplicate_detection_is_case_and_whitespace_insensitive():
    results = [
        _r("http://a.test/1", "CS 1301 Review", "Simpkins  is   great"),
        _r("http://b.test/2", "cs 1301 review", "simpkins is great"),
    ]
    deduped = dedupe_results(results)
    assert len(deduped) == 1


def test_near_identical_but_meaningfully_different_text_is_not_deduped():
    # One word changed ("great" -> "terrible") flips the content hash;
    # exact-content hashing intentionally does not fuzzy-match near-dupes
    # with different meaning - documented behavior, not a bug.
    results = [
        _r("http://a.test/1", "CS 1301 Review", "Simpkins is great this semester"),
        _r("http://b.test/2", "CS 1301 Review", "Simpkins is terrible this semester"),
    ]
    deduped = dedupe_results(results)
    assert len(deduped) == 2


def test_three_way_duplicate_across_domains_collapses_to_one():
    text = "Charles Simpkins is organized and helpful in office hours."
    results = [
        _r("http://forum-a.test/1", "Simpkins CS 1301", text),
        _r("http://forum-b.test/2", "Simpkins CS 1301", text),
        _r("http://forum-c.test/3", "Simpkins CS 1301", text),
    ]
    deduped = dedupe_results(results)
    assert len(deduped) == 1


def test_negated_neutral_keyword_does_not_emit_backwards_signal():
    # Adversarial-review finding: "homework heavy" is a sentiment-neutral
    # phrase VADER has no opinion on, so negating it ("not homework heavy")
    # produces compound=0.0 - not enough for VADER's own negation handling
    # to save us. Before the fix, this silently scored as "heavier"
    # workload (backwards) via the magnitude-default fallback. Now it must
    # emit no signal at all rather than the wrong one.
    assert extract_traits("This class is not homework heavy.") == []


def test_negation_does_not_suppress_keywords_that_already_contain_not():
    # "not too much work" is manageable_workload's OWN keyword phrase, not
    # a negation of a different one - it must still fire normally.
    signals = extract_traits("This class is not too much work, very manageable.")
    assert any(s.trait == "manageable_workload" for s in signals)


def test_relevance_requires_last_name_not_just_first_name():
    # A post mentioning a different "Charles" should not be tagged as
    # discussing this professor just because a common first name appears.
    result = _r("http://a.test/1", "My professor Charles", "Charles Nguyen was tough but fair in CS 1301")
    mentions_prof, _ = tag_relevance(result, "Charles Simpkins", "CS 1301")
    assert mentions_prof is False
