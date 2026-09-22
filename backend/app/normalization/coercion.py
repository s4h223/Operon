"""Type coercion helpers: dates, currency amounts, ids."""
from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd

_AMOUNT_STRIP_RE = re.compile(r"[^0-9.\-()]")
_CURRENCY_CODE_RE = re.compile(r"[A-Za-z]{3}")


def coerce_amount(value) -> float | None:
    """Parse a currency-formatted string ("$1,234.56", "(500.00)", "1.2e3")
    into a float. Parenthesized amounts are treated as negative (common
    accounting convention). Returns None if unparseable."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    negative = s.startswith("(") and s.endswith(")")
    cleaned = _AMOUNT_STRIP_RE.sub("", s)
    cleaned = cleaned.replace("(", "").replace(")", "")
    if cleaned in ("", "-", "."):
        return None
    try:
        amount = float(cleaned)
    except ValueError:
        return None
    return -abs(amount) if negative else amount


def coerce_date(value) -> date | None:
    """Parse a wide variety of date formats into a date, returning None if
    unparseable. Tries pandas' flexible parser (handles ISO, US, EU-ish
    formats and Excel serials) then falls back to dayfirst parsing."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s or s.lower() in ("nan", "nat", "none", "null"):
        return None
    for dayfirst in (False, True):
        try:
            ts = pd.to_datetime(s, errors="raise", dayfirst=dayfirst)
            return ts.date()
        except Exception:  # noqa: BLE001
            continue
    return None


def coerce_currency_code(value, default: str = "USD") -> str:
    if value is None:
        return default
    s = str(value).strip().upper()
    if not s or s in ("NAN", "NONE", "NULL"):
        return default
    match = _CURRENCY_CODE_RE.match(s)
    return match.group(0) if match else default


def coerce_str(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    s = str(value).strip()
    return s if s else None


def coerce_int(value) -> int | None:
    amount = coerce_amount(value)
    return int(round(amount)) if amount is not None else None


# ---- Vectorized (Series-level) variants ---------------------------------
#
# The scalar functions above are correct but, called once per cell via
# `.map()`, don't scale past tens of thousands of rows (each call re-invokes
# the Python interpreter, regex engine, and for dates a fresh dateutil parse).
# These operate on a whole column at once using pandas/numpy's vectorized C
# paths, which is 10-50x faster and is what the normalization pipeline uses.

_PAREN_RE = re.compile(r"^\(.*\)$")


def coerce_amount_series(s: pd.Series) -> pd.Series:
    s = s.astype("string")
    negative_mask = s.str.strip().str.match(_PAREN_RE).fillna(False)
    cleaned = s.str.replace(r"[^0-9.\-]", "", regex=True)
    cleaned = cleaned.mask(cleaned.isin(["", "-", "."]))
    values = pd.to_numeric(cleaned, errors="coerce")
    return values.where(~negative_mask, -values.abs())


_KNOWN_DATE_FORMATS = (
    "%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%d/%m/%Y", "%Y/%m/%d", "%b %d, %Y", "%d %b %Y",
)


def coerce_date_series(s: pd.Series) -> pd.Series:
    """Parse a column that may mix several date formats row-to-row (as many
    real-world exports do). pandas' vectorized to_datetime infers a single
    format from the first value and applies it to the whole column, silently
    turning every other format into NaT -- so instead we try each known
    format vectorized in turn, narrowing to only the still-unparsed rows each
    pass, and only fall back to a (slow, per-cell) flexible parse for the
    small remainder no known format matched."""
    s = s.astype("string").str.strip()
    s = s.mask(s.str.lower().isin(["nan", "nat", "none", "null", ""]))

    parsed = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    remaining = s.notna()
    for fmt in _KNOWN_DATE_FORMATS:
        if not remaining.any():
            break
        attempt = pd.to_datetime(s[remaining], format=fmt, errors="coerce")
        found = attempt.notna()
        idx = attempt.index[found]
        parsed.loc[idx] = attempt.loc[idx]
        remaining.loc[idx] = False

    if remaining.any():
        fallback = pd.to_datetime(s[remaining], errors="coerce", dayfirst=False)
        parsed.loc[fallback.index] = fallback

    return parsed.dt.date


def coerce_currency_series(s: pd.Series, default: str = "USD") -> pd.Series:
    s = s.astype("string").str.strip().str.upper()
    codes = s.str.extract(r"^([A-Za-z]{3})", expand=False)
    return codes.fillna(default)


def coerce_str_series(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.strip()
    s = s.where(s != "", None)
    return s.astype(object).where(s.notna(), None)


def coerce_int_series(s: pd.Series) -> pd.Series:
    return coerce_amount_series(s).round().astype("Int64")


SERIES_COERCERS = {
    "str": coerce_str_series,
    "date": coerce_date_series,
    "amount": coerce_amount_series,
    "int": coerce_int_series,
    "currency": coerce_currency_series,
}
