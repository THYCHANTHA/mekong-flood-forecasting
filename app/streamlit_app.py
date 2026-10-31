"""Mekong discharge forecasting research prototype: dashboard.

Every number shown is GloFAS v4 reanalysis discharge (model-simulated), not a river-gauge measurement.
No flood thresholds or warnings are shown: this is not an early-warning system.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
NAVY, BLUE, LIGHT = "#0b1f4a", "#2f80ed", "#9cc9f5"
MODEL_COLOURS = {"persistence": "#8a94a6", "seasonal_naive": "#c9d3e0", "climatology": "#b8c4d6",
                 "arima_anomaly": BLUE, "gradient_boosting": NAVY}
BANNER = ("MODEL-SIMULATED DATA: all discharge values are GloFAS v4 reanalysis output, not river-gauge "
          "measurements. Scores are agreement with GloFAS, not real-world forecast accuracy. "
          "This prototype is not a flood warning system.")


@st.cache_data
def load():
    hist = pd.read_csv(ROOT / "data/glofas_kratie_daily.csv", parse_dates=["timestamp"])
    meta = json.loads((ROOT / "data/glofas_kratie_daily.meta.json").read_text())
    pred = pd.read_parquet(ROOT / "results/predictions_test.parquet")
    met = pd.read_csv(ROOT / "results/metrics_test.csv")
    mon = pd.read_csv(ROOT / "results/monthly_errors_test.csv")
    resid = pd.read_csv(ROOT / "results/residual_diagnostics_test.csv")
    info = json.loads((ROOT / "results/run_info.json").read_text())
    quality = json.loads((ROOT / "results/data_quality.json").read_text())
    return hist, meta, pred, met, mon, resid, info, quality


def style(fig, height=380):
    fig.update_layout(template="simple_white", height=height, margin={"l": 10, "r": 10, "t": 40, "b": 10},
                      font={"color": NAVY}, legend={"orientation": "h", "y": -0.2})
    return fig


def page_overview(hist, meta, met, info, quality):
    st.header("Overview")
    st.write("Research prototype for day-ahead to two-week-ahead forecasting of **simulated** Mekong discharge at a "
             "main-stem grid cell near Kratie, Cambodia. It compares simple baselines, an ARIMA model on "
             "climatology-removed anomalies and gradient boosting under strictly chronological validation.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Daily values", f"{quality['rows']:,}")
    c2.metric("Period", f"{quality['start'][:4]}-{quality['end'][:4]}")
    c3.metric("Median (m3/s)", f"{quality['median']:,.0f}")
    c4.metric("Source type", meta["kind"].upper())
    best = met[met.horizon == 7].sort_values("MAE").iloc[0]
    st.info(f"At a 7-day horizon on the test period the lowest MAE is {best.MAE:,.0f} m3/s ({best.model}). "
            "This is agreement with a simulated series; see Limitations.")
    st.caption("Architecture: GloFAS adapter and an MRC adapter interface (authorised data only) feed one common "
               "schema, so models can later run on measured gauge data without rewriting.")


def page_history(hist, meta):
    st.header("Discharge history and location")
    fig = go.Figure(go.Scatter(x=hist.timestamp, y=hist.discharge, mode="lines", line={"color": BLUE, "width": 1}))
    fig.update_layout(title="Daily discharge (m3/s), GloFAS v4 reanalysis - model-simulated", yaxis_title="m3/s")
    st.plotly_chart(style(fig), width="stretch")
    clim = hist.assign(doy=hist.timestamp.dt.dayofyear).groupby("doy").discharge.agg(
        median="median", q10=lambda s: s.quantile(0.1), q90=lambda s: s.quantile(0.9)).reset_index()
    f2 = go.Figure()
    f2.add_trace(go.Scatter(x=clim.doy, y=clim.q90, line={"width": 0}, showlegend=False))
    f2.add_trace(go.Scatter(x=clim.doy, y=clim.q10, fill="tonexty", fillcolor="rgba(156,201,245,0.5)",
                            line={"width": 0}, name="10-90% range"))
    f2.add_trace(go.Scatter(x=clim.doy, y=clim["median"], line={"color": NAVY}, name="median"))
    f2.update_layout(title="Seasonal cycle by day of year (1997-2025, simulated)", xaxis_title="day of year",
                     yaxis_title="m3/s")
    st.plotly_chart(style(f2, 320), width="stretch")
    fm = go.Figure(go.Scattermap(
        lat=[meta["latitude"]], lon=[meta["longitude"]], mode="markers+text",
        marker=go.scattermap.Marker(size=22, color=NAVY), text=["GloFAS cell (main stem near Kratie)"],
        textposition="top right", hovertext=[meta["station_id"]]))
    fm.update_layout(map={"style": "open-street-map", "center": {"lat": meta["latitude"], "lon": meta["longitude"]},
                          "zoom": 7}, height=360, margin={"l": 0, "r": 0, "t": 0, "b": 0})
    st.plotly_chart(fm, width="stretch")
    st.caption(f"Grid cell {meta['latitude']:.3f} N, {meta['longitude']:.3f} E (5 km grid, snapped by the API). "
               "The nominal Kratie coordinates snap to a tributary cell; this main-stem cell was found by scanning.")


def page_forecasts(pred):
    st.header("Forecast results (test period)")
    c1, c2 = st.columns(2)
    h = c1.selectbox("Forecast horizon (days)", sorted(pred.horizon.unique()), index=2)
    models = c2.multiselect("Models", sorted(pred.model.unique()),
                            default=["persistence", "arima_anomaly", "gradient_boosting"])
    d = pred[pred.horizon == h]
    lo, hi = d.target_date.min().date(), d.target_date.max().date()
    start, end = st.slider("Target dates", min_value=lo, max_value=hi,
                           value=(pd.Timestamp("2019-06-01").date(), pd.Timestamp("2019-11-30").date()))
    d = d[(d.target_date >= pd.Timestamp(start)) & (d.target_date <= pd.Timestamp(end))]
    fig = go.Figure()
    truth = d[d.model == "persistence"].sort_values("target_date")
    fig.add_trace(go.Scatter(x=truth.target_date, y=truth.y_true, name="GloFAS (target)", line={"color": "black"}))
    for m in models:
        g = d[d.model == m].sort_values("target_date")
        fig.add_trace(go.Scatter(x=g.target_date, y=g.y_pred, name=m, line={"color": MODEL_COLOURS[m], "width": 1.4}))
    fig.update_layout(title=f"{h}-day-ahead forecasts vs simulated GloFAS discharge", yaxis_title="m3/s")
    st.plotly_chart(style(fig, 420), width="stretch")
    st.caption("Forecasts are issued h days before the target date using only data available at that time.")


def page_models(met, mon, resid):
    st.header("Model comparison and error metrics")
    show = met.copy()
    for c in ("MAE", "RMSE", "bias"):
        show[c] = show[c].round(0)
    show["NSE"] = show["NSE"].round(3)
    show["skill vs persistence"] = show["MAE_skill_vs_persistence"].round(3)
    show["95% interval"] = [f"[{a:.2f}, {b:.2f}]" if pd.notna(a) else "-"
                            for a, b in zip(show.skill_ci95_low, show.skill_ci95_high, strict=True)]
    st.dataframe(show[["model", "horizon", "n", "MAE", "RMSE", "NSE", "bias", "skill vs persistence", "95% interval"]],
                 hide_index=True, width="stretch")
    st.caption("MAE/RMSE in m3/s against simulated GloFAS. Skill = 1 - MAE/MAE(persistence); the interval is a "
               "30-day block bootstrap. Seasonal naive and climatology depend only on the target date, so they are "
               "the same at every horizon.")
    sel = met[met.model.isin(["persistence", "arima_anomaly", "gradient_boosting"])]
    fig = px.line(sel, x="horizon", y="MAE", color="model", markers=True, color_discrete_map=MODEL_COLOURS)
    fig.update_layout(title="MAE by forecast horizon (m3/s, test period)", xaxis={"tickvals": [1, 3, 7, 14]})
    st.plotly_chart(style(fig), width="stretch")
    h = st.selectbox("Horizon for monthly errors", sorted(mon.horizon.unique()), index=2)
    mm = mon[(mon.horizon == h) & mon.model.isin(["persistence", "arima_anomaly", "gradient_boosting"])]
    f2 = px.line(mm, x="month", y="MAE", color="model", markers=True, color_discrete_map=MODEL_COLOURS)
    f2.update_layout(title=f"MAE by month of target date, {h}-day horizon (m3/s)", xaxis={"dtick": 1})
    st.plotly_chart(style(f2, 320), width="stretch")
    st.subheader("Residual patterns")
    st.dataframe(resid.round(3), hide_index=True, width="stretch")
    st.caption("Lag-1 residual autocorrelation is high at longer horizons: errors persist for days, as expected "
               "when the models do not anticipate sudden rises.")


def page_data_limits(meta, quality, info):
    st.header("Data source, methodology and limitations")
    st.subheader("Data source")
    st.write(f"**Source:** {meta['source']}  \n**Type:** {meta['kind']} (model output, not a gauge)  \n"
             f"**Cell:** {meta['station_id']} ({meta['latitude']:.3f} N, {meta['longitude']:.3f} E)  \n"
             f"**Retrieved (UTC):** {meta['retrieved_at_utc']}  \n**Unit:** {meta['unit']}  \n"
             f"**Attribution:** {meta['attribution']}")
    st.json({k: quality[k] for k in ("start", "end", "rows", "duplicate_timestamps", "missing_values",
                                     "continuous_daily", "min", "median", "max")})
    st.subheader("Methodology")
    st.write(f"Chronological split: train {info['splits']['train'][0]} to {info['splits']['train'][1]}, validation "
             f"{info['splits']['validation'][0]} to {info['splits']['validation'][1]}, test from "
             f"{info['splits']['test'][0]}. Hyper-parameters were chosen on validation only; final models were "
             "refitted on train+validation and scored once on the test period. Features use only past values.")
    st.subheader("Limitations")
    st.markdown("- Target is simulated discharge: scores measure agreement with GloFAS, not accuracy against real river flow.\n"
                "- The series has unusual features at this cell (very low dry-season minima in some years and abrupt "
                "day-to-day jumps) that were not checked against gauge data.\n"
                "- One grid cell, one model version (GloFAS v4 consolidated), 1997-2025; no rainfall or upstream inputs.\n"
                "- Peaks are under-predicted and lagged; there are no uncertainty bands and no thresholds.\n"
                "- Not an operational or early-warning system.")


def main():
    st.set_page_config(page_title="Mekong Discharge Forecasting (simulated)", layout="wide")
    st.markdown(f"<style>.sim-banner{{background:#eaf3fd;border-left:6px solid {BLUE};padding:10px 14px;"
                f"color:{NAVY};font-weight:600;border-radius:4px}}</style><div class='sim-banner'>{BANNER}</div>",
                unsafe_allow_html=True)
    st.title("Mekong Discharge Forecasting")
    hist, meta, pred, met, mon, resid, info, quality = load()
    pages = ["Overview", "History and location", "Forecasts", "Model comparison", "Data and limitations"]
    wanted = st.query_params.get("page", "")  # allows deep links such as ?page=Forecasts (used for screenshots)
    page = st.sidebar.radio("Page", pages, index=pages.index(wanted) if wanted in pages else 0)
    if page == "Overview":
        page_overview(hist, meta, met, info, quality)
    elif page == "History and location":
        page_history(hist, meta)
    elif page == "Forecasts":
        page_forecasts(pred)
    elif page == "Model comparison":
        page_models(met, mon, resid)
    else:
        page_data_limits(meta, quality, info)


main()
