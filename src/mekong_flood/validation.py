"""Data-quality validation for one daily discharge series in the common schema."""
from __future__ import annotations

import pandas as pd

from .schema import single_kind, validate_schema


class DataQualityError(ValueError):
    """A hard data-quality failure (the series must not be modelled)."""


def validate_series(df: pd.DataFrame, *, max_missing_fraction: float = 0.02) -> dict:
    """Check schema, units, duplicates, continuity, negatives and missing values.

    Hard failures raise DataQualityError. Missing values are reported, never imputed here.
    Returns a report dict that is stored next to the results.
    """
    df = validate_schema(df)
    kind = single_kind(df)
    ids = df["station_id"].unique()
    if len(ids) != 1:
        raise DataQualityError(f"expected one station/cell, found {len(ids)}")
    dup = int(df["timestamp"].duplicated().sum())
    if dup:
        raise DataQualityError(f"{dup} duplicate timestamps")
    s = df.sort_values("timestamp")
    if not s["timestamp"].equals(df["timestamp"]):
        raise DataQualityError("timestamps are not in chronological order")
    full = pd.date_range(s["timestamp"].iloc[0], s["timestamp"].iloc[-1], freq="D")
    gaps = full.difference(pd.DatetimeIndex(s["timestamp"]))
    if len(gaps):
        raise DataQualityError(f"{len(gaps)} missing daily timestamps, first {gaps[0].date()}")
    q = s["discharge"]
    if (q.dropna() < 0).any():
        raise DataQualityError("negative discharge values")
    n_missing = int(q.isna().sum())
    if n_missing / len(q) > max_missing_fraction:
        raise DataQualityError(f"{n_missing} missing values exceeds {max_missing_fraction:.0%}")
    return {
        "station_id": str(ids[0]), "kind": kind, "source": str(s["source"].iloc[0]),
        "unit": str(s["unit"].iloc[0]), "start": str(s["timestamp"].iloc[0].date()),
        "end": str(s["timestamp"].iloc[-1].date()), "rows": len(s),
        "duplicate_timestamps": dup, "missing_daily_timestamps": 0, "missing_values": n_missing,
        "negative_values": 0, "min": float(q.min()), "median": float(q.median()),
        "max": float(q.max()), "continuous_daily": True,
    }


def trim_to_valid_span(df: pd.DataFrame) -> pd.DataFrame:
    """Drop the leading/trailing NaN run (e.g. GloFAS rows before the first value exists)."""
    ok = df["discharge"].notna()
    if not ok.any():
        raise DataQualityError("series has no values")
    first, last = ok.idxmax(), ok[::-1].idxmax()
    return df.loc[first:last].reset_index(drop=True)
