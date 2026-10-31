"""Mekong River Commission (MRC) observed discharge adapter: interface only.

MRC APIs require authentication and historical data are released through MRC's own access
process. This adapter never contacts MRC and never looks for credentials. It maps a file that
the owner has obtained from MRC through the authorised route onto the common schema, with
kind="observation", so models can later run on it unchanged. See docs/MRC_DATA_REQUEST.md.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ..schema import UNIT, validate_schema
from .base import DischargeSource


class MRCAccessRequired(RuntimeError):
    """Raised when no authorised MRC data file has been supplied."""


class MRCAdapter(DischargeSource):
    kind = "observation"
    name = "MRC (authorised export)"

    def __init__(self, path: Path | None, *, station_id: str, latitude: float, longitude: float,
                 date_column: str = "date", value_column: str = "discharge",
                 unit_column: str | None = "unit", licence_note: str = ""):
        self.path = Path(path) if path else None
        self.station_id, self.latitude, self.longitude = station_id, latitude, longitude
        self.date_column, self.value_column, self.unit_column = date_column, value_column, unit_column
        self.licence_note = licence_note

    def load(self) -> pd.DataFrame:
        if self.path is None or not self.path.exists():
            raise MRCAccessRequired(
                "No authorised MRC export supplied. Obtain observed discharge from MRC through its data "
                "request process (docs/MRC_DATA_REQUEST.md); this project does not bypass MRC access controls.")
        raw = pd.read_csv(self.path)
        if self.unit_column and self.unit_column in raw:
            units = set(raw[self.unit_column].astype(str).str.replace("³", "3").str.lower())
            if units - {"m3/s", "cms"}:
                raise ValueError(f"unsupported discharge unit(s) in MRC file: {sorted(units)}")
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()[:12]
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(raw[self.date_column]).dt.normalize(),
            "latitude": self.latitude, "longitude": self.longitude, "station_id": self.station_id,
            "discharge": pd.to_numeric(raw[self.value_column], errors="coerce"),
            "unit": UNIT, "source": self.name, "kind": self.kind,
            "retrieved_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "provenance": f"file sha256[:12]={digest} | observed gauge data | {self.licence_note}".strip(" |"),
        })
        return validate_schema(df.sort_values("timestamp").reset_index(drop=True))
