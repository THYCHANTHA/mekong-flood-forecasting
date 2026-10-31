# Mekong discharge forecasting: a research prototype on SIMULATED discharge

> **Read this first.** Every discharge value in this repository is **GloFAS v4 reanalysis output (model-simulated), not a river-gauge
> measurement.** All scores below are *model-to-model agreement with GloFAS*, not independent verification against real river
> flow. This prototype makes **no claim of real-world flood-forecasting accuracy**, defines no flood thresholds and is **not a
> flood warning system**. The architecture is built so that authorised MRC gauge observations can replace or supplement GloFAS
> later (`docs/MRC_DATA_REQUEST.md`).

Status: working core (data adapters, validation, baselines, ARIMA, gradient boosting, evaluation, dashboard). GitHub Actions
has never run for this repository (the account was billing-locked when it was published), so the CI workflow is untested.

## Abstract
The project forecasts daily discharge 1, 3, 7 and 14 days ahead at one 5 km grid cell on the main-stem Mekong near Kratie
(12.525 N, 105.925 E), using the GloFAS v4 consolidated reanalysis (1997-01-01 to 2025-05-31, 10,378 days, retrieved through the
Open-Meteo Flood API). Persistence, seasonal-naive and climatology baselines are compared with an ARIMA model on
climatology-removed log discharge and with gradient boosting, under strictly chronological training, validation and test
periods. On the test period (2018-01-01 to 2025-05-31, 2,708 days) both models beat persistence at every horizon, with an
MAE skill of 0.40 at 1 day for ARIMA and roughly 0.11 to 0.25 at 3 to 14 days for both models. ARIMA and gradient boosting show no meaningful
difference beyond 1 day. Errors are concentrated in the July to October high-flow season, and sharp
rises (such as the 2019 peak) are anticipated by none of the models.

## Research question and objectives
How well can simple statistical and machine-learning models forecast a simulated daily Mekong discharge series, and how should
a pipeline be organised so that real gauge observations can be substituted later without rewriting the models?
Objectives: (1) an adapter architecture with a common time-series schema and explicit simulation/observation labelling;
(2) validated, cached, documented data; (3) honest baselines and models with leakage-free chronological evaluation;
(4) a dashboard that always labels the data as simulated; (5) documented future work.

## Data
| Item | Value |
|---|---|
| Source | GloFAS v4 consolidated reanalysis (Copernicus Emergency Management Service), via the Open-Meteo Flood API (`models=consolidated_v4`) |
| Nature | **Simulation**: hydrological-model output on a 5 km grid, not a gauge |
| Cell | 12.525 N, 105.925 E (API-snapped cell centre 12.525002, 105.92502); a main-stem cell found by scanning, because the nominal Kratie coordinates snap to a tributary (0.39 m3/s in July 2020) |
| Period / size | 1997-01-01 to 2025-05-31, 10,378 daily values (values before 1997 are empty in this cell) |
| Retrieved | 2026-10-31 (UTC); raw payload cached with a SHA-256; committed copy is `data/glofas_kratie_daily.csv` |
| Quality checks | schema, unit, duplicates (0), daily continuity (complete), missing values (0), negatives (0); report in `results/data_quality.json` |
| Licence | CEMS-FLOODS licence (reuse and adaptation allowed with the notice "Contains modified Copernicus Emergency Management Service information 2026 (GloFAS v4)"; information only, not a warning); Open-Meteo data CC BY 4.0, free API for non-commercial use |
| Why `consolidated_v4` | the default "seamless" product also contains forecast-driven values; the consolidated product is identical to it in the overlap (checked on 2015-2020, maximum difference 0.0) |
| Version matters | GloFAS v3 and v4 give different values at the same cell and date (6,591 against 3,655 m3/s on 1997-01-01) |

Data caveats (not corrected, not checked against gauges): the simulated series has very low dry-season minima in some years (18.7 m3/s
minimum; 34, 19 and 21 m3/s in 2020, 2021 and 2024), a peak of 95,498 m3/s (2019), and abrupt dry-season day-to-day jumps (up to 2.6 times
the previous day). Whether these are realistic cannot be judged without gauge data.

## Architecture
```
GloFAS adapter  ─┐                                   ┌─> baselines, ARIMA, gradient boosting ─> evaluation ─> dashboard
                 ├─> common schema ─> validation ────┤
MRC adapter     ─┘   (kind: simulation | observation) └─> feature engineering (leakage-safe)
(interface; needs authorised file)
```
Common schema (`src/mekong_flood/schema.py`): timestamp, latitude, longitude, station/cell id, discharge, unit, source, kind
(`simulation` or `observation`), retrieval time and provenance. `combine()` refuses to mix simulated and observed series unless
the caller passes `allow_mixed=True` and a note describing how they differ; models refuse mixed series. The MRC adapter never
contacts MRC and never looks for credentials: it only reads a file that was obtained through MRC's authorised process.

## Method
- **Targets and features.** Direct multi-horizon forecasts of log discharge at 1, 3, 7 and 14 days. Features at origin t use only data
  up to t: lags 0, 1, 2, 3, 7, 14, 30, trailing 7- and 30-day means, 1- and 7-day differences, day-of-year sine/cosine.
- **Chronological split by target date.** Train 1997-01-01 to 2012-12-31, validation 2013-01-01 to 2017-12-31, test 2018-01-01 to
  2025-05-31. Hyper-parameters and the ARIMA order were chosen on validation only; the final models were refitted on train+validation
  and scored once on the test period. No random splitting.
- **Models.** Persistence; seasonal naive (value one year earlier); climatology (day-of-year geometric mean from training data);
  ARIMA(p,0,q) on log discharge minus the training day-of-year climatology (selected order (2,0,1) of {(1,0,0),(2,0,0),(2,0,1)}; not a
  seasonal ARIMA with a 365-day period); gradient boosting (scikit-learn `HistGradientBoostingRegressor`, one model per horizon,
  selected learning rate 0.05 and 15 leaves from a 4-point grid). XGBoost was not used: it is not installed and the scikit-learn
  implementation is sufficient for this data size.
- **Metrics** in m3/s: MAE, RMSE, Nash-Sutcliffe efficiency, bias, and MAE skill against persistence with a 95% interval from a
  30-day moving-block bootstrap. Forecasts are back-transformed from log space, so they tend towards the median rather than the mean.

## Results (test period 2018-01-01 to 2025-05-31, 2,708 target days; agreement with SIMULATED GloFAS discharge)
| Model | Horizon (days) | MAE (m3/s) | RMSE (m3/s) | NSE | Bias (m3/s) | MAE skill vs persistence [95% interval] |
|---|---|---|---|---|---|---|
| persistence | 1 | 806 | 1,974 | 0.978 | -4 | - |
| persistence | 3 | 2,019 | 4,401 | 0.888 | -12 | - |
| persistence | 7 | 3,110 | 6,171 | 0.781 | -18 | - |
| persistence | 14 | 4,346 | 7,999 | 0.631 | -21 | - |
| seasonal_naive | any | 4,881 | 9,086 | 0.524 | 348 | n/a (depends on horizon; see `results/metrics_test.csv`) |
| climatology | any | 3,881 | 6,878 | 0.727 | 62 | n/a (depends on horizon; see `results/metrics_test.csv`) |
| arima_anomaly | 1 | 483 | 1,488 | 0.987 | 25 | 0.40 [0.36, 0.44] |
| arima_anomaly | 3 | 1,744 | 4,361 | 0.890 | -59 | 0.14 [0.08, 0.18] |
| arima_anomaly | 7 | 2,761 | 5,490 | 0.826 | -270 | 0.11 [0.02, 0.18] |
| arima_anomaly | 14 | 3,301 | 6,248 | 0.775 | -277 | 0.24 [0.12, 0.33] |
| gradient_boosting | 1 | 589 | 1,756 | 0.982 | -33 | 0.27 [0.17, 0.35] |
| gradient_boosting | 3 | 1,745 | 3,964 | 0.909 | -330 | 0.14 [0.06, 0.20] |
| gradient_boosting | 7 | 2,718 | 5,397 | 0.832 | -507 | 0.13 [0.01, 0.21] |
| gradient_boosting | 14 | 3,264 | 6,359 | 0.767 | -562 | 0.25 [0.13, 0.34] |

Climatology and seasonal-naive forecasts depend only on the target date, so they are identical at every horizon (MAE 3,881 and 4,881 m3/s).

Findings from `results/` (all from the executed run):
- At 1 day, ARIMA is clearly the best model (MAE skill 0.40, interval 0.36 to 0.44, against 0.27 for gradient boosting).
- From 3 to 14 days, ARIMA and gradient boosting have practically the same error (the skill intervals overlap almost completely),
  and both beat persistence modestly (skill about 0.11 to 0.25). The 14-day improvement is largest in relative terms because persistence degrades fastest.
- Errors are concentrated in July to October. For gradient boosting at 7 days, MAE by month ranges from 149 m3/s (February) to 7,342 m3/s
  (September), and bias is strongly negative in September and October (about -2,700 and -3,000 m3/s): the models under-predict during high flow.
- Residuals are strongly autocorrelated at longer horizons (lag-1 autocorrelation 0.83 to 0.94 at 7 and 14 days): errors persist for days.
- The 2019 peak (95,498 m3/s) is anticipated by none of the models; they track it with a lag (`results/figures/forecast_2019.png`).
- Validation-period results are in `results/metrics_validation.csv`; they point the same way as the test results.

Figures: `results/figures/` (history, 2019 forecasts, error by horizon, monthly MAE). Dashboard screenshots: `results/screenshots/`
(captured from the running app; in the History page screenshot the location marker is not drawn by the headless browser, so the coordinates are given in text).

## Dashboard
`streamlit run app/streamlit_app.py` (binds to localhost only). Pages: overview, history and location, forecasts, model comparison
and residuals, data source and limitations. A banner on every page states that the data are model-simulated. It shows no thresholds or alerts.

## Reproduce
```
python -m venv .venv && .venv/Scripts/python -m pip install -e . pytest ruff
.venv/Scripts/python -m pytest -q                      # 28 tests, offline (uses committed data and results)
.venv/Scripts/python scripts/fetch_data.py             # optional: re-download (network); cached afterwards
.venv/Scripts/python scripts/run_experiment.py         # about 20 seconds
.venv/Scripts/python scripts/make_figures.py
.venv/Scripts/python -m streamlit run app/streamlit_app.py
```

## Tests
28 tests (`tests/`): schema and unit checks, mixed-kind refusal, data validation failures (duplicates, gaps, negatives, missing
values, several stations), GloFAS parsing/caching with no network, MRC adapter refusal without an authorised file and mapping of an
authorised export to the schema, features without lookahead, segments by target date, baseline definitions, a check that the
vectorised ARIMA forecasts equal statsmodels' own forecasts, metrics, and dashboard smoke tests on every page. The last full run
and linting results are in `results/test_run.txt`.

## Limitations
- The target is simulated. Skill against real discharge is unknown and may be very different.
- One grid cell, one GloFAS version, 1997 to May 2025; no rainfall, upstream flow or other cells.
- A single train/validation/test split, with strongly autocorrelated errors, so even the intervals understate uncertainty.
- Sharp rises and peaks are under-predicted and lagged; no uncertainty bands for individual forecasts.
- Data oddities in this cell (see Data) were not investigated against gauges.
- The 95% intervals come from a block bootstrap over one test period and are indicative only.

## Roadmap
See `docs/NEXT_STEPS.md` (MRC observations, multi-station, rainfall/upstream inputs, deep learning, independent validation, early-warning research).

## References and acknowledgements
- Copernicus Emergency Management Service, GloFAS river discharge reanalysis (CEMS-FLOODS licence); data accessed through Open-Meteo.com (CC BY 4.0).
- Contains modified Copernicus Emergency Management Service information 2026 (GloFAS v4).
- Software: pandas, NumPy, scikit-learn, statsmodels, Plotly, Streamlit, Matplotlib.

Code licence: MIT (`LICENSE`). The data keep their own licence, stated above.
