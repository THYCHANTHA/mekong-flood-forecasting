"""Load the committed daily series back into the common schema (no network, no cache needed)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .schema import UNIT, validate_schema


def save_compact(df: pd.DataFrame, csv_path: Path, meta_path: Path, extra: dict) -> None:
    """Store timestamp+discharge in a CSV and the constant schema fields once in a JSON file."""
    first = df.iloc[0]
    meta = {"latitude": float(first.latitude), "longitude": float(first.longitude),
            "station_id": first.station_id, "unit": first.unit, "source": first.source, "kind": first.kind,
            "retrieved_at_utc": first.retrieved_at_utc, "provenance": first.provenance, **extra}
    df[["timestamp", "discharge"]].to_csv(csv_path, index=False, date_format="%Y-%m-%d")
    meta_path.write_text(json.dumps(meta, indent=2))


def load_compact(csv_path: Path, meta_path: Path) -> pd.DataFrame:
    meta = json.loads(meta_path.read_text())
    raw = pd.read_csv(csv_path, parse_dates=["timestamp"])
    df = raw.assign(latitude=meta["latitude"], longitude=meta["longitude"], station_id=meta["station_id"],
                    unit=UNIT, source=meta["source"], kind=meta["kind"],
                    retrieved_at_utc=meta["retrieved_at_utc"], provenance=meta["provenance"])
    return validate_schema(df)
