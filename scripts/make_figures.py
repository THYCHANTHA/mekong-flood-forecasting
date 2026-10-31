"""Static figures for the README (all titled as SIMULATED GloFAS discharge)."""
from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
NAVY, BLUE, LIGHT, GREY = "#0b1f4a", "#2f80ed", "#9cc9f5", "#8a94a6"
COL = {"persistence": GREY, "seasonal_naive": "#c9d3e0", "climatology": "#b8c4d6",
       "arima_anomaly": BLUE, "gradient_boosting": NAVY}
TAG = "GloFAS v4 reanalysis (model-simulated, not gauge data)"


def main() -> None:
    fig_dir = ROOT / "results/figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    pred = pd.read_parquet(ROOT / "results/predictions_test.parquet")
    met = pd.read_csv(ROOT / "results/metrics_test.csv")
    mon = pd.read_csv(ROOT / "results/monthly_errors_test.csv")
    hist = pd.read_csv(ROOT / "data/glofas_kratie_daily.csv", parse_dates=["timestamp"]).set_index("timestamp")

    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.plot(hist.index, hist.discharge, color=BLUE, lw=0.6)
    ax.axvspan(pd.Timestamp("2018-01-01"), hist.index[-1], color=LIGHT, alpha=0.35, label="test period")
    ax.set_ylabel("discharge (m3/s)")
    ax.set_title(f"Daily discharge, Kratie main-stem cell - {TAG}", fontsize=10, color=NAVY)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(fig_dir / "history.png", dpi=110)
    plt.close(fig)

    g = pred[(pred.horizon == 7) & pred.model.isin(["gradient_boosting", "arima_anomaly", "persistence"])]
    lo, hi = pd.Timestamp("2019-06-01"), pd.Timestamp("2019-11-30")
    fig, ax = plt.subplots(figsize=(11, 3.8))
    truth = g[g.model == "persistence"].set_index("target_date")["y_true"].loc[lo:hi]
    ax.plot(truth.index, truth, color="black", lw=1.4, label="GloFAS (target)")
    for m in ("persistence", "arima_anomaly", "gradient_boosting"):
        s = g[g.model == m].set_index("target_date")["y_pred"].loc[lo:hi]
        ax.plot(s.index, s, color=COL[m], lw=1.0, label=m)
    ax.set_title(f"7-day-ahead forecasts, 2019 wet season (test period) - {TAG}", fontsize=10, color=NAVY)
    ax.set_ylabel("discharge (m3/s)")
    ax.legend(frameon=False, ncol=4)
    fig.tight_layout()
    fig.savefig(fig_dir / "forecast_2019.png", dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    for m, d in met[met.model.isin(["persistence", "arima_anomaly", "gradient_boosting"])].groupby("model"):
        ax[0].plot(d.horizon, d.MAE, marker="o", color=COL[m], label=m)
        ax[1].plot(d.horizon, d.RMSE, marker="o", color=COL[m], label=m)
    for a, t in zip(ax, ("MAE (m3/s)", "RMSE (m3/s)"), strict=True):
        a.set_xlabel("forecast horizon (days)")
        a.set_title(t, fontsize=10, color=NAVY)
        a.set_xticks([1, 3, 7, 14])
    ax[0].legend(frameon=False)
    fig.suptitle(f"Test-period error by horizon, agreement with {TAG}", fontsize=9, color=NAVY)
    fig.tight_layout()
    fig.savefig(fig_dir / "error_by_horizon.png", dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 3.6))
    for m in ("persistence", "arima_anomaly", "gradient_boosting"):
        d = mon[(mon.model == m) & (mon.horizon == 7)]
        ax.plot(d.month, d.MAE, marker="o", color=COL[m], label=m)
    ax.set_xticks(range(1, 13))
    ax.set_xlabel("month of target date")
    ax.set_ylabel("MAE (m3/s)")
    ax.set_title(f"7-day MAE by month (test) - {TAG}", fontsize=9, color=NAVY)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(fig_dir / "monthly_mae_h7.png", dpi=110)
    plt.close(fig)
    print("figures written:", sorted(p.name for p in fig_dir.glob("*.png")))


if __name__ == "__main__":
    main()
