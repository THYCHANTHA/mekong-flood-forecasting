# Data

`glofas_kratie_daily.csv` (+ `glofas_kratie_daily.meta.json`): daily river discharge in m3/s at one 5 km grid cell on the
main-stem Mekong near Kratie (12.525 N, 105.925 E), 1997-01-01 to 2025-05-31 (10,378 days).

- **Model-simulated, not gauge data.** It is GloFAS v4 consolidated reanalysis output (the `consolidated_v4` model), retrieved via
  the Open-Meteo Flood API on 2026-10-31 (UTC). Only reanalysis values are included, no forecast-driven values.
- **Licence and attribution.** Copernicus Emergency Management Service (CEMS-FLOODS licence): reproduction, distribution and adaptation
  are permitted with the notice "Contains modified Copernicus Emergency Management Service information 2026 (GloFAS v4)". The data
  are for information only and are not a flood warning. Open-Meteo states its data licence as CC BY 4.0 and its free API as non-commercial.
- **Regeneration.** `python scripts/fetch_data.py` rebuilds these files from the API (raw responses are cached in `data/raw/`, git-ignored).
  The API output can change over time, so the committed copy is the reference for the results in this repository.
- `data/mrc/` (if created) is for authorised MRC observations, which are git-ignored and never committed unless MRC permits it.
