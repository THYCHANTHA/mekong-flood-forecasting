# Data access findings (checked 2026-10-31)

Nothing has been modelled yet. This file records what could and could not be reached before any code is written.

## Observed water levels: Mekong River Commission (MRC)
| Check | Result |
|---|---|
| MRC Data Portal (`portal.mrcmekong.org`) and Near Real-time Monitoring (`monitoring.mrcmekong.org`) | reachable (HTTP 200); both are JavaScript single-page apps |
| `api.mrcmekong.org/api/v1/...` and `timeseries.api.mrcmekong.org/api/v1/...` | **HTTP 401 Unauthorized** without credentials (stations, time-series, telemetry endpoints) |
| Terms and data policy | not read; historical data is distributed through an account / data-request process (`datarequest.mrcmekong.org` is referenced by the portal) |

**Conclusion:** observed MRC water levels are *not* openly available to this project. Credentials were not sought or extracted
from the web application's code (that would bypass the access control). To use MRC observations the owner must obtain access
through MRC (account or data request) and confirm what may be published.

## Open alternative: GloFAS v4 reanalysis river discharge (Copernicus Emergency Management Service)
| Item | Finding |
|---|---|
| Access | free API from Open-Meteo (`flood-api.open-meteo.com/v1/flood`, no key; free tier is for non-commercial use with call limits); upstream product: CEMS GloFAS historical dataset |
| What it is | **simulated** daily river discharge on a 5 km grid (hydrological model forced by meteorological reanalysis), **not** gauge observations |
| Main-stem cell near Kratie | 12.525 N, 105.925 E (27,351.68 m3/s on the sampled August 2020 day). The API's nearest-river snapping is unreliable: the nominal Kratie coordinates returned a tributary cell (0.39 m3/s in July 2020). The cell was found by scanning a 7 x 7 grid at 0.05 degree spacing. |
| Coverage in that cell | 15,639 daily rows requested from 1984-01-01; non-null from 1997-01-01 (10,890 values to 2026-10-25), nulls before 1997 |
| Licence (read from the CEMS-FLOODS licence PDF) | free access with reproduction, distribution, communication to the public and adaptation allowed; notice required: "Generated using Copernicus Emergency Management Service information [Year]" or, if modified, "Contains modified Copernicus Emergency Management Service information [Year]"; data are for information only and are **not a flood warning**; no warranty |
| Not yet checked | Open-Meteo's own data-use wording (the page text was client-rendered and gave no licence sentence); whether the cell's long-run discharge matches published Kratie statistics (no verified reference gathered yet) |

## Consequences for the scientific claim
Forecasting a model-simulated discharge series measures how well a statistical model emulates GloFAS, not how well it
predicts real river flow. Skill against observations cannot be claimed without gauge data. Any results from this source
must say "GloFAS reanalysis discharge" everywhere (README, figures, tables) and the project remains a research prototype,
not an emergency warning system.

## CHIRPS rainfall (already verified in Project 01)
`data.chc.ucsb.edu/products/CHIRPS/v3.0/...` reachable (HTTP 200); licence recorded in the Project 01 repository. Rainfall over
Cambodia explains only part of Mekong flow (a large share originates upstream), so it is a secondary predictor.
