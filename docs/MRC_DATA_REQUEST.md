# Requesting observed MRC data (future integration)

**Status:** not requested yet. This project does not use MRC observations. The MRC APIs return HTTP 401 without
credentials, and this repository neither bypasses that nor contains any MRC credential.

## Route
Historical hydrological data from the Mekong River Commission (MRC) is released through MRC's own access process (the MRC
data portal refers to a data-request service at `datarequest.mrcmekong.org`). Confirm the current procedure, any
registration and the terms of use on the MRC pages before requesting; this guide records what to ask for, not MRC's rules.

## Information to include in a request
| Item | What to ask for / state |
|---|---|
| Purpose | Non-commercial academic research prototype on river-discharge forecasting; results may be published |
| Station(s) | Main-stem Mekong stations in or near Cambodia (for example Kratie, and upstream/downstream stations). Ask MRC for the authoritative station list, identifiers, coordinates and the gauge-zero datum |
| Variable | Daily discharge in m3/s (preferred). If only daily water level is provided, also ask for the rating curve (stage-discharge relation), its validity period and its uncertainty |
| Period | As long as possible, at least 1997 to the present, to overlap the GloFAS series (1997-01-01 to 2025-05-31 in this repository) |
| Resolution | Daily means (state the day boundary and time zone) |
| Quality | Quality flags, gap and estimation markers, and how infilled values were produced |
| Terms | Whether results, derived series and figures may be published, whether the raw data may be redistributed (otherwise keep them local and git-ignored), and the required citation/acknowledgement |
| Format | CSV or similar with a date column, a discharge column and a unit column |

## Short request template
> I am preparing an academic research prototype on forecasting Mekong River discharge in Cambodia and would like to
> request daily observed discharge (m3/s) for [stations], period [from] to [to], with quality flags, station metadata
> (coordinates, datum) and, if discharge is derived from stage, the rating curve information. Please also confirm the
> terms for publishing derived results and for redistributing the data. The data will be used only for research and the
> source will be acknowledged as you require.

## Integration once authorised data are received
1. Keep the file local (`data/mrc/`, git-ignored) unless MRC states that redistribution is permitted.
2. Load it with `MRCAdapter(path, station_id=..., latitude=..., longitude=..., licence_note=...)`. The adapter validates the unit,
   marks every row `kind="observation"` and records the file hash as provenance.
3. Run `validate_series` and the same chronological experiment. Models only see the common schema, so no model code changes.
4. Report observed and simulated results separately. `schema.combine` refuses to mix them unless `allow_mixed=True` and a note
   describing the differences is supplied (a gauge measures a river cross-section, GloFAS is a 5 km grid-cell simulation).
5. Do not describe results as real-world forecast skill until they are computed against these observations.
