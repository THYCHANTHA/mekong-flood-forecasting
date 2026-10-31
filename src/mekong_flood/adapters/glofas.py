"""GloFAS v4 reanalysis river discharge (Copernicus EMS) via the Open-Meteo Flood API.

SIMULATED discharge on a 5 km grid, not a gauge measurement. Only the `consolidated_v4` model is
used (reanalysis); the default "seamless" product also contains forecast-driven values.
Raw API responses are cached on disk with a SHA-256 so a run never repeats the request.
"""
from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ..schema import UNIT, validate_schema
from ..validation import trim_to_valid_span
from .base import DischargeSource

API = "https://flood-api.open-meteo.com/v1/flood"
# Main-stem Mekong cell near Kratie, found by scanning (the nominal Kratie coordinates snap to a
# tributary). The API snaps requests to the nearest 5 km grid cell; this is the cell it returns.
KRATIE_CELL = {"latitude": 12.525, "longitude": 105.925, "station_id": "glofas_v4_cell_12.525N_105.925E"}
MODEL = "consolidated_v4"
ATTRIBUTION = ("Contains modified Copernicus Emergency Management Service information 2026 "
               "(GloFAS v4), retrieved via Open-Meteo.com (CC BY 4.0).")


class GloFASOpenMeteo(DischargeSource):
    kind = "simulation"
    name = "GloFAS v4 consolidated via Open-Meteo"

    def __init__(self, cache_dir: Path, start: str = "1984-01-01", end: str = "2025-12-31",
                 cell: dict | None = None, fetch=None):
        self.cache_dir = Path(cache_dir)
        self.start, self.end = start, end
        self.cell = cell or KRATIE_CELL
        self._fetch = fetch or self._http_get  # injectable for offline tests

    def _url(self) -> str:
        q = {"latitude": self.cell["latitude"], "longitude": self.cell["longitude"],
             "daily": "river_discharge", "start_date": self.start, "end_date": self.end,
             "models": MODEL}
        return f"{API}?{urllib.parse.urlencode(q)}"

    @staticmethod
    def _http_get(url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=120) as r:
            return r.read()

    def _raw(self) -> tuple[bytes, str, bool]:
        """Return (payload, retrieved_at_utc, from_cache). Network only on a cache miss."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        url = self._url()
        key = hashlib.sha256(url.encode()).hexdigest()[:16]
        body, meta = self.cache_dir / f"glofas_{key}.json", self.cache_dir / f"glofas_{key}.meta.json"
        if body.exists() and meta.exists():
            return body.read_bytes(), json.loads(meta.read_text())["retrieved_at_utc"], True
        payload = self._fetch(url)
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        body.write_bytes(payload)
        meta.write_text(json.dumps({
            "retrieved_at_utc": stamp, "url": url, "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload), "model": MODEL, "attribution": ATTRIBUTION}, indent=2))
        return payload, stamp, False

    def load(self) -> pd.DataFrame:
        payload, stamp, _ = self._raw()
        return self.parse(payload, stamp, self._url())

    def parse(self, payload: bytes, retrieved_at: str, url: str) -> pd.DataFrame:
        d = json.loads(payload)
        units = d.get("daily_units", {}).get("river_discharge")
        if units not in ("m³/s", "m3/s"):
            raise ValueError(f"unexpected discharge unit from API: {units!r}")
        daily = d["daily"]
        digest = hashlib.sha256(payload).hexdigest()[:12]
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(daily["time"]),
            "latitude": float(d["latitude"]), "longitude": float(d["longitude"]),
            "station_id": self.cell["station_id"],
            "discharge": pd.to_numeric(pd.Series(daily["river_discharge"]), errors="coerce"),
            "unit": UNIT, "source": self.name, "kind": self.kind,
            "retrieved_at_utc": retrieved_at,
            "provenance": f"{url} | payload sha256[:12]={digest} | simulated, not a gauge",
        })
        return validate_schema(trim_to_valid_span(df))
