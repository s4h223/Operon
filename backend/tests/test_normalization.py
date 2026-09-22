from app.modules.normalization import (
    normalize_professor_name,
    professor_key,
    normalize_course_code,
    course_key,
)


def test_normalize_professor_name_last_first_format():
    assert normalize_professor_name("Simpkins, Charles A") == "Charles Simpkins"


def test_normalize_professor_name_plain_format():
    assert normalize_professor_name("Dr. Charlie Simpkins") == "Charlie Simpkins"


def test_professor_key_collapses_variants():
    variants = [
        "Simpkins, Charles A",
        "Charles Simpkins",
        "Professor Charles Simpkins",
        "Dr. Charles A. Simpkins",
    ]
    keys = {professor_key(v) for v in variants}
    assert keys == {"charles_simpkins"}


def test_professor_key_distinguishes_different_people():
    assert professor_key("Charles Simpkins") != professor_key("David Simpkins")
    assert professor_key("Alice Zhou") != professor_key("Alice Zhang")


def test_normalize_course_code_variants():
    assert normalize_course_code("CS 1301") == "CS 1301"
    assert normalize_course_code("CS1301") == "CS 1301"
    assert normalize_course_code("cs-1301") == "CS 1301"
    assert normalize_course_code("cs   1301") == "CS 1301"
    assert normalize_course_code("MATH 1552") == "MATH 1552"
    assert normalize_course_code("ISYE2027") == "ISYE 2027"


def test_course_key_matches_across_formats():
    assert course_key("CS 1301") == course_key("cs-1301") == course_key("CS1301")


def test_course_key_distinguishes_different_courses():
    assert course_key("CS 1301") != course_key("CS 1331")
