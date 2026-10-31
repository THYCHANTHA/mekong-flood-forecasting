"""Descriptive look at the GloFAS series before modelling (annual cycle, extremes, odd values)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
s = pd.read_csv(ROOT / "data/glofas_kratie_daily.csv", parse_dates=["timestamp"]).set_index("timestamp")["discharge"]
print("percentiles (m3/s):", {p: round(float(s.quantile(p / 100)), 1) for p in (0, 1, 5, 25, 50, 75, 95, 99, 100)})
print("days < 500:", int((s < 500).sum()), "| days < 1000:", int((s < 1000).sum()))
ann = s.groupby(s.index.year).agg(["min", "median", "max", "count"]).round(0)
print(ann.to_string())
print("monthly median:", s.groupby(s.index.month).median().round(0).to_dict())
low = s[s < 500]
print("low-flow dates:", low.index.min(), low.index.max(), "n years with low:", sorted(set(low.index.year)))
d = s.pct_change().abs()
print("largest 1-day relative changes:", d.nlargest(5).round(2).to_dict())
