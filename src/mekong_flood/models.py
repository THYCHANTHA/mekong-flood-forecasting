"""Baselines and models. All forecast log discharge for horizon h; callers back-transform.

- persistence:     q(t+h) = q(t)
- seasonal naive:  q(t+h) = q(t+h-365)        (same calendar day one year earlier; observed at t for h <= 365)
- climatology:     geometric mean for the day of year, training segment only
- ARIMA on anomalies: ARIMA(p,0,q) on log discharge minus the training day-of-year climatology.
  The annual cycle is removed by the climatology, so this is not a SARIMA with a 365-day period.
- gradient boosting: scikit-learn HistGradientBoostingRegressor, one direct model per horizon.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from statsmodels.tsa.arima.model import ARIMA


def persistence(logq: pd.Series, origins: pd.DatetimeIndex, h: int) -> np.ndarray:
    return logq.reindex(origins).to_numpy()


def seasonal_naive(logq: pd.Series, origins: pd.DatetimeIndex, h: int, period: int = 365) -> np.ndarray:
    if h > period:
        raise ValueError("horizon exceeds the seasonal period")
    return logq.shift(period - h).reindex(origins).to_numpy()


def doy_climatology(logq_train: pd.Series, smooth: int = 15) -> np.ndarray:
    """Mean log discharge per day of year (index doy-1, length 366), circularly smoothed."""
    g = logq_train.groupby(logq_train.index.dayofyear).mean().reindex(range(1, 367)).interpolate(limit_direction="both")
    v = g.to_numpy()
    pad = smooth
    ext = np.concatenate([v[-pad:], v, v[:pad]])
    sm = pd.Series(ext).rolling(smooth, center=True, min_periods=1).mean().to_numpy()[pad:-pad]
    return sm


def climatology_forecast(clim: np.ndarray, origins: pd.DatetimeIndex, h: int) -> np.ndarray:
    target = origins + pd.Timedelta(days=h)
    return clim[target.dayofyear.to_numpy() - 1]


class AnomalyARIMA:
    """ARIMA(p,0,q) on climatology-removed log discharge, parameters fixed after fitting on training data."""

    def __init__(self, order: tuple[int, int, int]):
        self.order = order
        self.clim: np.ndarray | None = None
        self.params = None

    def fit(self, logq_train: pd.Series) -> AnomalyARIMA:
        self.clim = doy_climatology(logq_train)
        anom = logq_train.to_numpy() - self.clim[logq_train.index.dayofyear.to_numpy() - 1]
        self.params = ARIMA(anom, order=self.order, trend="n").fit().params
        return self

    def _anomalies(self, logq: pd.Series) -> np.ndarray:
        return logq.to_numpy() - self.clim[logq.index.dayofyear.to_numpy() - 1]

    def forecast_all(self, logq: pd.Series, horizons: tuple[int, ...]) -> dict[int, pd.Series]:
        """h-step log-discharge forecasts from EVERY origin in `logq`, using only data up to the origin.

        Parameters stay fixed; the Kalman filter is run over the series and the filtered state at
        origin t is propagated h steps (Z T^h a_t), then the climatology of the target day is added back.
        """
        res = ARIMA(self._anomalies(logq), order=self.order, trend="n").filter(self.params)
        fr = res.filter_results
        state = fr.filtered_state                      # (k_states, nobs): uses data up to each t only
        Z, T = fr.design[:, :, 0], fr.transition[:, :, 0]
        out = {}
        for h in horizons:
            anom_h = (Z @ np.linalg.matrix_power(T, h) @ state).ravel()
            target = logq.index + pd.Timedelta(days=h)
            out[h] = pd.Series(anom_h + self.clim[target.dayofyear.to_numpy() - 1], index=logq.index)
        return out


def fit_gbm(X: pd.DataFrame, y: pd.Series, params: dict) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(random_state=0, **params).fit(X, y)
