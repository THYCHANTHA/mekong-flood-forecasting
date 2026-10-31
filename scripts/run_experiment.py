"""Chronological experiment on the SIMULATED GloFAS discharge series.

train 1997-01-01..2012-12-31, validation 2013..2017, test 2018-01-01..end. Hyper-parameters and ARIMA
order are chosen on validation only; the final models are refitted on train+validation and scored once on
the test period. Performance is model-to-model agreement with GloFAS, not verification against gauges.
"""
from __future__ import annotations

import json
import platform
import time
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import statsmodels

from mekong_flood import evaluate as ev
from mekong_flood import features as ft
from mekong_flood import models as md
from mekong_flood.data_io import load_compact
from mekong_flood.schema import single_kind
from mekong_flood.validation import validate_series

ROOT = Path(__file__).resolve().parents[1]
TRAIN_END, VAL_END = "2012-12-31", "2017-12-31"
ARIMA_ORDERS = [(1, 0, 0), (2, 0, 0), (2, 0, 1)]
GBM_GRID = [{"learning_rate": lr, "max_leaf_nodes": leaves, "max_iter": 300, "min_samples_leaf": 40}
            for lr, leaves in product((0.05, 0.1), (15, 31))]


def long_frame(model: str, h: int, origins: pd.DatetimeIndex, y_log: np.ndarray, p_log: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({"model": model, "horizon": h, "origin": origins,
                         "target_date": origins + pd.Timedelta(days=h),
                         "y_true": np.exp(y_log), "y_pred": np.exp(p_log)})


def main() -> None:
    t0 = time.time()
    df = load_compact(ROOT / "data/glofas_kratie_daily.csv", ROOT / "data/glofas_kratie_daily.meta.json")
    quality = validate_series(df)
    assert single_kind(df) == "simulation"
    logq = ft.log_series(df)
    seg = ft.segments(TRAIN_END, VAL_END)
    data = {h: ft.build_dataset(logq, h) for h in ft.HORIZONS}
    mask = {h: {k: ft.in_segment(data[h][2], b) for k, b in seg.items()} for h in ft.HORIZONS}

    def baseline_frames(segment: str, fit_name: str) -> list[pd.DataFrame]:
        clim = md.doy_climatology(logq[: seg[fit_name][1]])
        out = []
        for h in ft.HORIZONS:
            X, y, _ = data[h]
            m = mask[h][segment]
            o, yy = X.index[m], y.to_numpy()[m]
            sn = md.seasonal_naive(logq, o, h)
            keep = ~np.isnan(sn)
            out += [long_frame("persistence", h, o, yy, md.persistence(logq, o, h)),
                    long_frame("climatology", h, o, yy, md.climatology_forecast(clim, o, h)),
                    long_frame("seasonal_naive", h, o[keep], yy[keep], sn[keep])]
        return out

    def arima_frames(segment: str, fit_name: str, order) -> list[pd.DataFrame]:
        a = md.AnomalyARIMA(order).fit(logq[: seg[fit_name][1]])
        fc = a.forecast_all(logq, ft.HORIZONS)
        out = []
        for h in ft.HORIZONS:
            X, y, _ = data[h]
            m = mask[h][segment]
            o = X.index[m]
            out.append(long_frame(f"arima{order}", h, o, y.to_numpy()[m], fc[h].reindex(o).to_numpy()))
        return out

    def gbm_frames(segment: str, fit_name: str, params: dict) -> list[pd.DataFrame]:
        out = []
        for h in ft.HORIZONS:
            X, y, _ = data[h]
            fit_m, m = mask[h][fit_name], mask[h][segment]
            model = md.fit_gbm(X[fit_m], y[fit_m], params)
            out.append(long_frame("gradient_boosting", h, X.index[m], y.to_numpy()[m], model.predict(X[m])))
        return out

    # ---- model selection on validation (fit on train only) ----
    def mean_mae(frames: list[pd.DataFrame]) -> float:
        p = pd.concat(frames)
        return float(np.mean([ev.mae(g.y_true, g.y_pred) for _, g in p.groupby("horizon")]))

    arima_val = {o: mean_mae(arima_frames("val", "train", o)) for o in ARIMA_ORDERS}
    best_order = min(arima_val, key=arima_val.get)
    gbm_val = [{"params": p, "val_mean_MAE": mean_mae(gbm_frames("val", "train", p))} for p in GBM_GRID]
    best_gbm = min(gbm_val, key=lambda r: r["val_mean_MAE"])["params"]
    val_pred = pd.concat(baseline_frames("val", "train") + arima_frames("val", "train", best_order)
                         + gbm_frames("val", "train", best_gbm), ignore_index=True)

    # ---- final: refit on train+validation, score on test once ----
    test_pred = pd.concat(baseline_frames("test", "trainval") + arima_frames("test", "trainval", best_order)
                          + gbm_frames("test", "trainval", best_gbm), ignore_index=True)
    test_pred["model"] = test_pred["model"].replace({f"arima{best_order}": "arima_anomaly"})
    val_pred["model"] = val_pred["model"].replace({f"arima{best_order}": "arima_anomaly"})

    # same origins for every model within a horizon (seasonal naive may lack the first year; test has it)
    summary = ev.summarise(test_pred)
    summary_val = ev.summarise(val_pred)
    resid = ev.residual_diagnostics(test_pred)
    monthly = ev.monthly_errors(test_pred)
    boot = []
    for h in ft.HORIZONS:
        g = test_pred[test_pred.horizon == h]
        ref = g[g.model == "persistence"].set_index("origin")["y_pred"]
        for m in g.model.unique():
            if m == "persistence":
                continue
            gm = g[g.model == m].sort_values("origin")
            lo, hi = ev.block_bootstrap_skill(gm.y_true.to_numpy(), gm.y_pred.to_numpy(),
                                              ref.reindex(gm.origin).to_numpy())
            boot.append({"model": m, "horizon": h, "skill_ci95_low": lo, "skill_ci95_high": hi})
    summary = summary.merge(pd.DataFrame(boot), on=["model", "horizon"], how="left")

    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    test_pred.to_parquet(out / "predictions_test.parquet", index=False)
    summary.to_csv(out / "metrics_test.csv", index=False)
    summary_val.to_csv(out / "metrics_validation.csv", index=False)
    resid.to_csv(out / "residual_diagnostics_test.csv", index=False)
    monthly.to_csv(out / "monthly_errors_test.csv", index=False)
    info = {"target": "GloFAS v4 consolidated discharge (SIMULATED), Kratie main-stem cell",
            "splits": {"train": ["1997-01-01", TRAIN_END], "validation": ["2013-01-01", VAL_END],
                       "test": ["2018-01-01", quality["end"]]},
            "horizons_days": list(ft.HORIZONS), "arima_validation_mean_MAE": {str(k): v for k, v in arima_val.items()},
            "arima_selected_order": list(best_order), "gbm_validation": gbm_val, "gbm_selected": best_gbm,
            "test_origins": int(test_pred[test_pred.horizon == 1].model.value_counts().iloc[0]),
            "runtime_s": round(time.time() - t0, 1),
            "versions": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
                         "scikit-learn": sklearn.__version__, "statsmodels": statsmodels.__version__},
            "interpretation": "Scores are agreement with a simulated series (model-to-model), not verification against river gauges."}
    (out / "run_info.json").write_text(json.dumps(info, indent=2, default=str))
    pd.set_option("display.width", 200)
    print(json.dumps({k: info[k] for k in ("arima_selected_order", "gbm_selected", "runtime_s", "test_origins")}))
    print(summary.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
