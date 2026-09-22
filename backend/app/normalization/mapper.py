"""Suggest a raw-column -> standard-field mapping using the alias dictionary
plus fuzzy string matching as a fallback for unrecognized column names."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from app.normalization.field_aliases import (
    build_reverse_alias_index,
    normalize_column_name,
)


@dataclass
class FieldSuggestion:
    standard_field: str | None
    confidence: float
    alternatives: list[str] = field(default_factory=list)


def suggest_mapping(entity_type: str, raw_columns: list[str]) -> dict[str, FieldSuggestion]:
    reverse_index = build_reverse_alias_index(entity_type)
    known_aliases = list(reverse_index.keys())

    suggestions: dict[str, FieldSuggestion] = {}
    claimed_standard_fields: set[str] = set()

    # Pass 1: exact normalized alias matches (highest confidence).
    unresolved: list[str] = []
    for raw_col in raw_columns:
        norm = normalize_column_name(raw_col)
        if norm in reverse_index:
            standard_field = reverse_index[norm]
            suggestions[raw_col] = FieldSuggestion(standard_field=standard_field, confidence=1.0)
            claimed_standard_fields.add(standard_field)
        else:
            unresolved.append(raw_col)

    # Pass 2: fuzzy match against known aliases for unresolved columns.
    for raw_col in unresolved:
        norm = normalize_column_name(raw_col)
        matches = difflib.get_close_matches(norm, known_aliases, n=3, cutoff=0.6)
        if matches:
            best = matches[0]
            standard_field = reverse_index[best]
            score = difflib.SequenceMatcher(None, norm, best).ratio()
            alternatives = [reverse_index[m] for m in matches[1:] if reverse_index[m] != standard_field]
            suggestions[raw_col] = FieldSuggestion(
                standard_field=standard_field, confidence=round(score, 3), alternatives=alternatives
            )
        else:
            suggestions[raw_col] = FieldSuggestion(standard_field=None, confidence=0.0)

    return suggestions


def missing_required_fields(
    entity_type: str, mapping: dict[str, str], required_fields: list[str]
) -> list[str]:
    mapped_standard_fields = set(mapping.values())
    return [f for f in required_fields if f not in mapped_standard_fields]
