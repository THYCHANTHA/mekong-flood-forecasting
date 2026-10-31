"""Metrics in m3/s space, per horizon, plus residual diagnostics and a block-bootstrap interval."""
from __future__ import annotations

import numpy as np
import pandas as pd


def mae(y, p) -> float:
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(p))))


def rmse(y, p) -> float:
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


def nse(y, p) -> float:
    y, p = np.asarray(y), np.asarray(p)
    return float(1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2))


def summarise(pred: pd.DataFrame) -> pd.DataFrame:
    """pred columns: model, horizon, origin, target_date, y_true, y_pred (m3/s)."""
    rows = []
    pers = pred[pred.model == "persistence"].set_index(["horizon", "origin"])["y_pred"]
    for (m, h), g in pred.groupby(["model", "horizon"]):
        ref = pers.loc[h].reindex(g["origin"]).to_numpy()
        rows.append({"model": m, "horizon": h, "n": len(g), "MAE": mae(g.y_true, g.y_pred),
                     "RMSE": rmse(g.y_true, g.y_pred), "NSE": nse(g.y_true, g.y_pred),
                     "bias": float(np.mean(g.y_pred - g.y_true)),
                     "MAE_skill_vs_persistence": 1 - mae(g.y_true, g.y_pred) / mae(g.y_true, ref)})
    return pd.DataFrame(rows)


def block_bootstrap_skill(y, p_model, p_ref, block: int = 30, n_boot: int = 1000, seed: int = 0) -> tuple[float, float]:
    """95% interval for 1 - MAE(model)/MAE(reference), resampling contiguous blocks of days."""
    e_m, e_r = np.abs(np.asarray(y) - p_model), np.abs(np.asarray(y) - p_ref)
    n = len(e_m)
    n_blocks = int(np.ceil(n / block))
    rng = np.random.default_rng(seed)
    skills = np.empty(n_boot)
    for i in range(n_boot):
        starts = rng.integers(0, n - block + 1, n_blocks)
        idx = (starts[:, None] + np.arange(block)).ravel()[:n]
        skills[i] = 1 - e_m[idx].mean() / e_r[idx].mean()
    return float(np.percentile(skills, 2.5)), float(np.percentile(skills, 97.5))


def residual_diagnostics(pred: pd.DataFrame) -> pd.DataFrame:
    """Bias and MAE by calendar month, and lag-1 residual autocorrelation, per model and horizon."""
    p = pred.assign(resid=pred.y_pred - pred.y_true, month=pd.to_datetime(pred.target_date).dt.month)
    rows = []
    for (m, h), g in p.groupby(["model", "horizon"]):
        g = g.sort_values("origin")
        r = g["resid"].to_numpy()
        ac1 = float(np.corrcoef(r[:-1], r[1:])[0, 1]) if len(r) > 2 else float("nan")
        rows.append({"model": m, "horizon": h, "resid_lag1_autocorr": ac1})
    return pd.DataFrame(rows)


def monthly_errors(pred: pd.DataFrame) -> pd.DataFrame:
    p = pred.assign(resid=pred.y_pred - pred.y_true, abs_err=(pred.y_pred - pred.y_true).abs(),
                    month=pd.to_datetime(pred.target_date).dt.month)
    return p.groupby(["model", "horizon", "month"]).agg(bias=("resid", "mean"), MAE=("abs_err", "mean"),
                                                        n=("resid", "size")).reset_index()
