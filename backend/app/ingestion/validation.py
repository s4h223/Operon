"""Structural validation of an uploaded CSV, before/independent of mapping."""
from __future__ import annotations

import pandas as pd


def validate_dataframe(df: pd.DataFrame) -> list[str]:
    warnings: list[str] = []

    if df.empty:
        warnings.append("File contains no data rows.")
        return warnings

    if len(df.columns) != len(set(df.columns)):
        dupes = df.columns[df.columns.duplicated()].tolist()
        warnings.append(f"Duplicate column names detected: {sorted(set(dupes))}")

    fully_blank_cols = [c for c in df.columns if df[c].isna().all()]
    if fully_blank_cols:
        warnings.append(f"Columns with no data in any row: {fully_blank_cols}")

    blank_rows = int(df.isna().all(axis=1).sum())
    if blank_rows:
        warnings.append(f"{blank_rows} fully blank row(s) will be dropped.")

    unnamed = [c for c in df.columns if str(c).lower().startswith("unnamed")]
    if unnamed:
        warnings.append(f"Unnamed/empty header columns detected: {unnamed}")

    return warnings
