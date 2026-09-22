"""Normalize professor names and course codes across heterogeneous sources.

Georgia Tech sources spell the same thing differently:
- Oscar/registration: "Simpkins, Charles A"  (Last, First Middle)
- Course Critique:    "Charles Simpkins"
- Reddit:             "Simpkins", "Prof Simpkins", "Dr. Charlie Simpkins"
- Course code:        "CS 1301", "CS1301", "cs-1301", "CS  1301"

`professor_key` and `course_key` are the canonical join keys used
everywhere else in the pipeline.
"""
from __future__ import annotations

import re
import unicodedata

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "phd", "ph.d"}
_TITLES = {"dr", "dr.", "prof", "prof.", "professor", "mr", "mr.", "mrs", "mrs.", "ms", "ms."}


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def _tokenize_name(raw: str) -> list[str]:
    raw = _strip_accents(raw).lower()
    raw = raw.replace(",", " ")
    tokens = re.findall(r"[a-z']+", raw)
    tokens = [t for t in tokens if t not in _TITLES and t.strip(".") not in _SUFFIXES]
    return tokens


def _first_last_order(raw: str) -> str:
    """Reorder "Last, First Middle" (Oscar-style) to "First Middle Last".
    No-op when there's no comma (already assumed First ... Last order).
    """
    raw = raw.strip()
    if "," not in raw:
        return raw
    last, _, rest = raw.partition(",")
    return f"{rest.strip()} {last.strip()}".strip()


def _core_name_tokens(raw: str) -> list[str]:
    """First + last name tokens, dropping titles, suffixes and single-letter
    middle initials. Returns [first, last] or [only_token]."""
    tokens = _tokenize_name(_first_last_order(raw))
    if not tokens:
        return []
    core = [tokens[0]] + [t for t in tokens[1:] if len(t) > 1]
    if len(core) >= 2:
        return [core[0], core[-1]]
    return core


def normalize_professor_name(raw: str) -> str:
    """Return a display-friendly normalized name: 'First Last'."""
    if not raw or not raw.strip():
        return ""
    tokens = _core_name_tokens(raw)
    if not tokens:
        return raw.strip()
    return " ".join(t.capitalize() for t in tokens)


def professor_key(raw: str) -> str:
    """Canonical join key: lowercase 'first_last' ignoring titles/middle
    initials, honorifics and punctuation. Two spellings of the same person
    should collapse to the same key; two different people should not.
    """
    return "_".join(_core_name_tokens(raw))


_SUBJECT_ALIASES = {
    "computer science": "CS",
    "mathematics": "MATH",
    "accounting": "ACCT",
    "industrial and systems engineering": "ISYE",
}


def normalize_course_code(raw: str) -> str:
    """Return canonical 'SUBJ NNNN' form, e.g. 'CS 1301'."""
    if not raw:
        return ""
    raw = raw.strip().upper()
    raw = _SUBJECT_ALIASES.get(raw.lower(), raw)
    match = re.match(r"^([A-Z]{2,4})\s*[-\s]?\s*(\d{3,4}[A-Z]?)$", raw)
    if not match:
        # try splitting on non-alphanumeric boundary generically
        letters = re.match(r"^([A-Z]+)", raw)
        digits = re.search(r"(\d{3,4}[A-Z]?)", raw)
        if letters and digits:
            return f"{letters.group(1)} {digits.group(1)}"
        return raw
    subject, number = match.groups()
    return f"{subject} {number}"


def course_key(raw: str) -> str:
    return normalize_course_code(raw).replace(" ", "").lower()
