"""Leakage-safe features and targets for direct multi-horizon forecasting of log discharge.

Every feature at origin t uses only values observed at or before t (trailing windows, positive
shifts). The target for horizon h is log discharge at t+h. Samples are assigned to the chronological
train/validation/test segments by TARGET date, so no training label lies in a later segment.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HORIZONS = (1, 3, 7, 14)
LAGS = (0, 1, 2, 3, 7, 14, 30)
ROLLS = (7, 30)


def log_series(df: pd.DataFrame) -> pd.Series:
    s = df.set_index("timestamp")["discharge"].astype(float)
    if s.isna().any() or (s <= 0).any():
        raise ValueError("log transform needs a complete, strictly positive series")
    return np.log(s).rename("logq")


def feature_frame(logq: pd.Series) -> pd.DataFrame:
    f = pd.DataFrame(index=logq.index)
    for lag in LAGS:
        f[f"lag{lag}"] = logq.shift(lag)
    for w in ROLLS:
        f[f"roll_mean{w}"] = logq.rolling(w).mean()
    f["diff1"] = logq - logq.shift(1)
    f["diff7"] = logq - logq.shift(7)
    doy = logq.index.dayofyear.to_numpy()
    f["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    f["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return f


def build_dataset(logq: pd.Series, h: int) -> tuple[pd.DataFrame, pd.Series, pd.DatetimeIndex]:
    """(X, y, target_dates) with rows dropped where a feature or the target is unavailable."""
    X = feature_frame(logq)
    y = logq.shift(-h).rename(f"logq_t+{h}")
    ok = X.notna().all(axis=1) & y.notna()
    X, y = X[ok], y[ok]
    return X, y, y.index + pd.Timedelta(days=h)


def segments(train_end: str, val_end: str) -> dict[str, tuple[pd.Timestamp | None, pd.Timestamp | None]]:
    te, ve = pd.Timestamp(train_end), pd.Timestamp(val_end)
    return {"train": (None, te), "val": (te + pd.Timedelta(days=1), ve),
            "trainval": (None, ve), "test": (ve + pd.Timedelta(days=1), None)}


def in_segment(target_dates: pd.DatetimeIndex, bounds: tuple) -> np.ndarray:
    lo, hi = bounds
    m = np.ones(len(target_dates), dtype=bool)
    if lo is not None:
        m &= target_dates >= lo
    if hi is not None:
        m &= target_dates <= hi
    return m
