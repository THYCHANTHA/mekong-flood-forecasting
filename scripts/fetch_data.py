"""Fetch (or reuse the cache of) GloFAS v4 consolidated discharge at the Kratie main-stem cell,
validate it and write data/glofas_kratie_daily.csv (+ .meta.json) and results/data_quality.json.

Network is used only on a cache miss (data/raw/, git-ignored).
"""
from __future__ import annotations

import json
from pathlib import Path

from mekong_flood.adapters.glofas import ATTRIBUTION, KRATIE_CELL, MODEL, GloFASOpenMeteo
from mekong_flood.data_io import save_compact
from mekong_flood.validation import validate_series

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    src = GloFASOpenMeteo(ROOT / "data/raw")
    payload, stamp, cached = src._raw()
    df = src.parse(payload, stamp, src._url())
    report = validate_series(df)
    report.update({"model_parameter": MODEL, "requested_cell": KRATIE_CELL, "retrieved_at_utc": stamp,
                   "served_from_cache": cached, "attribution": ATTRIBUTION,
                   "note": "GloFAS discharge is model-simulated (reanalysis), not a gauge measurement."})
    save_compact(df, ROOT / "data/glofas_kratie_daily.csv", ROOT / "data/glofas_kratie_daily.meta.json",
                 {"attribution": ATTRIBUTION, "model_parameter": MODEL})
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results/data_quality.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
