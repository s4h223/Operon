"""CSV parsing utilities: read raw uploads into pandas, with permissive
dtype handling since real-world exports mix types, quoting styles, and
encodings."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


class CsvParseError(Exception):
    pass


def read_csv_flexible(path: Path, nrows: int | None = None) -> pd.DataFrame:
    """Read a CSV robustly: try utf-8 first, fall back to latin-1, and
    tolerate ragged rows by skipping ones that fail to parse."""
    read_kwargs = dict(
        dtype=str,  # read everything as string; normalization layer coerces types
        keep_default_na=False,
        na_values=["", "NA", "N/A", "null", "NULL", "None"],
        skip_blank_lines=True,
        on_bad_lines="skip",
        engine="c",  # the pure-python engine is >10x slower and doesn't scale
    )
    if nrows is not None:
        read_kwargs["nrows"] = nrows

    try:
        return pd.read_csv(path, encoding="utf-8", **read_kwargs)
    except UnicodeDecodeError:
        pass
    except pd.errors.EmptyDataError as e:
        raise CsvParseError(f"File is empty: {e}") from e

    try:
        return pd.read_csv(path, encoding="latin-1", **read_kwargs)
    except pd.errors.EmptyDataError as e:
        raise CsvParseError(f"File is empty: {e}") from e
    except Exception as e:  # noqa: BLE001 - surfaced to API caller as validation error
        raise CsvParseError(f"Could not parse CSV: {e}") from e


def dataframe_preview(df: pd.DataFrame, n: int = 20) -> list[dict]:
    preview = df.head(n).copy()
    return preview.where(pd.notnull(preview), None).to_dict(orient="records")
