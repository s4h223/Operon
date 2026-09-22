"""Layer 5/6 QA: professor-name and course-code normalization edge cases
beyond the happy-path cases already in test_normalization.py."""
from app.modules.normalization import (
    normalize_professor_name,
    professor_key,
    normalize_course_code,
    course_key,
)


# --- professor name edge cases -------------------------------------------

def test_hyphenated_last_name_collapses_consistently():
    a = professor_key("Smith-Jones, Patricia")
    b = professor_key("Patricia Smith-Jones")
    assert a == b


def test_apostrophe_in_name_is_handled():
    # O'Brien: the tokenizer only keeps [a-z'] so the apostrophe survives.
    key = professor_key("O'Brien, Michael")
    assert key == professor_key("Michael O'Brien")
    assert key  # non-empty


def test_accented_characters_are_normalized():
    assert professor_key("José García") == professor_key("Jose Garcia")


def test_single_name_professor_does_not_crash():
    # Rare but real: mononym instructor listings ("STAFF" aside).
    assert professor_key("Madonna") == "madonna"
    assert normalize_professor_name("Madonna") == "Madonna"


def test_empty_and_whitespace_only_names():
    assert professor_key("") == ""
    assert professor_key("   ") == ""
    assert normalize_professor_name("") == ""
    assert normalize_professor_name("   ") == ""


def test_name_with_multiple_middle_names_still_collapses_to_first_last():
    a = professor_key("Charles Michael Andrew Simpkins")
    b = professor_key("Simpkins, Charles M A")
    assert a == b == "charles_simpkins"


def test_phd_and_suffix_titles_stripped():
    assert professor_key("Charles Simpkins, PhD") == professor_key("Charles Simpkins")
    assert professor_key("Charles Simpkins Jr") == professor_key("Charles Simpkins")


def test_all_caps_and_all_lowercase_names_collapse():
    assert professor_key("CHARLES SIMPKINS") == professor_key("charles simpkins") == "charles_simpkins"


def test_extra_internal_whitespace_does_not_change_key():
    assert professor_key("Charles    Simpkins") == "charles_simpkins"


# --- course code edge cases -----------------------------------------------

def test_course_code_lowercase_no_space():
    assert normalize_course_code("acct2101") == "ACCT 2101"


def test_course_code_with_letter_suffix_section():
    # Some GT courses have letter-suffixed catalog numbers (e.g. labs).
    assert normalize_course_code("CS 4903A") == "CS 4903A"


def test_course_code_extra_whitespace_and_dashes():
    assert normalize_course_code("  math -- 1552  ") in ("MATH 1552", "MATH -- 1552")
    # the primary, expected normalized form:
    assert normalize_course_code("MATH-1552") == "MATH 1552"


def test_course_key_case_and_spacing_insensitive():
    variants = ["PHYS 2211", "phys2211", "Phys-2211", "phys   2211"]
    keys = {course_key(v) for v in variants}
    assert keys == {"phys2211"}


def test_course_code_five_letter_subject_falls_back_gracefully():
    # Subjects are 2-4 letters at GT; a malformed 5+ letter subject should
    # not crash, even if it doesn't match the primary regex.
    result = normalize_course_code("HISTORY 1101")
    assert "1101" in result


def test_course_code_garbage_input_does_not_crash():
    assert normalize_course_code("???") == "???"
    assert normalize_course_code(None or "") == ""
