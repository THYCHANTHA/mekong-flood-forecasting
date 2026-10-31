"""Common time-series schema shared by every discharge source.

One row = one daily discharge value at one station or grid cell. Simulated (model) and observed
(gauge) series carry different `kind` values and must never be mixed silently.
"""
from __future__ import annotations

import pandas as pd

COLUMNS = [
    "timestamp",       # observation date (UTC, daily), pandas datetime64[ns]
    "latitude",        # decimal degrees (for GloFAS: the snapped grid-cell centre)
    "longitude",
    "station_id",      # gauge identifier or grid-cell identifier
    "discharge",       # float, in `unit`; NaN if missing
    "unit",            # "m3/s"
    "source",          # e.g. "GloFAS v4 consolidated via Open-Meteo", "MRC"
    "kind",            # "simulation" or "observation"
    "retrieved_at_utc",  # ISO 8601 time of retrieval
    "provenance",      # short text: URL/parameters/payload hash or file hash
]
KINDS = ("simulation", "observation")
UNIT = "m3/s"


class SchemaError(ValueError):
    """The frame does not follow the common schema."""


class MixedKindError(ValueError):
    """Simulated and observed discharge were combined without an explicit decision."""


def validate_schema(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"missing columns: {missing}")
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        raise SchemaError("timestamp must be datetime64")
    if not pd.api.types.is_numeric_dtype(df["discharge"]):
        raise SchemaError("discharge must be numeric")
    bad = set(df["kind"].unique()) - set(KINDS)
    if bad:
        raise SchemaError(f"unknown kind values: {sorted(bad)}")
    if set(df["unit"].unique()) != {UNIT}:
        raise SchemaError(f"unit must be {UNIT!r}, found {sorted(df['unit'].unique())}")
    return df[COLUMNS]


def single_kind(df: pd.DataFrame) -> str:
    """Return the one `kind` present; refuse mixed series (use `combine` to mix on purpose)."""
    kinds = set(df["kind"].unique())
    if len(kinds) != 1:
        raise MixedKindError(f"series mixes kinds {sorted(kinds)}; models need a single kind")
    return kinds.pop()


def combine(frames: list[pd.DataFrame], *, allow_mixed: bool = False, note: str = "") -> pd.DataFrame:
    """Concatenate frames. Mixing simulation and observation requires allow_mixed=True and a note."""
    out = pd.concat(frames, ignore_index=True)
    if len(set(out["kind"])) > 1:
        if not allow_mixed or not note.strip():
            raise MixedKindError(
                "refusing to combine simulated and observed discharge without allow_mixed=True "
                "and a note documenting how they differ")
        out.attrs["mixed_kind_note"] = note
    return out
