# Next steps and future improvements (the "20% document" part)

Development strategy for this project: about 80% building a working core (genuine data, a suitable model, real
evaluation, essential tests, honest documentation) and about 20% documenting what is deferred. Items here are deliberately
not built yet.

## Blocked on an owner decision
- Choose the target series: (a) MRC observed water levels, which needs MRC access or a data request and confirmation of
  redistribution terms, or (b) GloFAS v4 reanalysis discharge, openly available but simulated (see `DATA_ACCESS.md`).

## Planned after the core exists
- Baselines first: persistence and seasonal-naive; then SARIMA and a gradient-boosted model on lagged features; an LSTM
  only if it beats those under walk-forward validation.
- Walk-forward (expanding window) evaluation by hydrological year; report MAE, RMSE, NSE and skill against persistence at
  1-, 3- and 7-day horizons, with per-season breakdown (flood season versus dry season).
- Upstream and rainfall predictors (CHIRPS), once their lead-lag value is shown to help on a validation period.
- Multiple main-stem cells and a gauge-to-grid cross-check, once observed data are available.
- Uncertainty intervals (quantile regression or conformal prediction).
- A small Streamlit page with the forecast, errors and caveats.

## Out of scope
Operational warnings, inundation mapping, and any claim of real-world forecast skill without gauge validation.
