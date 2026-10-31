# Next steps and future improvements (the "20% document" part)

Strategy for this project: about 80% building a working core (genuine data, suitable models, real evaluation, essential
tests, honest documentation) and about 20% documenting what is deferred. Nothing below is implemented yet.

## 1. Observed river-gauge data (highest value)
- Request MRC observations following `docs/MRC_DATA_REQUEST.md`; confirm redistribution and publication terms.
- Run the existing chronological experiment on `MRCAdapter` data and report it separately from GloFAS results.
- Cross-check the GloFAS cell against the gauge (bias, timing, peak size) before trusting any simulated result.
  The simulated cell shows very low dry-season minima in some years and abrupt day-to-day jumps that have not been checked.

## 2. Multi-station forecasting
- Add upstream and downstream stations or grid cells and forecast with their lagged values as inputs (travel-time structure).
- Choose cells through the river network, not by nominal coordinates (the nominal Kratie coordinates snap to a tributary).

## 3. Rainfall and upstream-flow integration
- Add CHIRPS rainfall (already verified as an open source in Project 01) and upstream discharge, and test whether they help
  on the validation period before using them. Most Mekong flow originates upstream of Cambodia.

## 4. Spatial hydrological analysis
- Catchment-level aggregation of rainfall, flow-path and sub-basin features; relation to the Tonle Sap system.

## 5. Better models
- Quantile regression or conformal prediction for uncertainty bands.
- Models trained on peaks (the current models under-predict and lag sharp rises).
- LSTM or other deep-learning models only if they beat the gradient-boosting baseline under walk-forward validation.
- Walk-forward (expanding window) refitting each year instead of a single train/validation/test split.

## 6. Independent real-world validation
- Compare against gauge data from more than one source and period; report skill by season and flow regime.

## 7. Potential operational early-warning research
- Only after validation against observations, with institutional partners, flood-impact definitions and thresholds supplied
  by the responsible agencies. This prototype defines no thresholds and issues no warnings.

## Out of scope for now
Operational warnings, inundation mapping, and any claim of real-world forecast skill without gauge validation.
