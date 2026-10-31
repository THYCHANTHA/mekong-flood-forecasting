"""Offline tests: schema, validation, adapters, features/splits, baselines, ARIMA, metrics."""
import json

import numpy as np
import pandas as pd
import pytest
from statsmodels.tsa.arima.model import ARIMA

from mekong_flood import evaluate as ev
from mekong_flood import features as ft
from mekong_flood import models as md
from mekong_flood.adapters.glofas import GloFASOpenMeteo
from mekong_flood.adapters.mrc import MRCAccessRequired, MRCAdapter
from mekong_flood.data_io import load_compact, save_compact
from mekong_flood.schema import COLUMNS, MixedKindError, SchemaError, combine, single_kind, validate_schema
from mekong_flood.validation import DataQualityError, trim_to_valid_span, validate_series


def make_frame(n=800, kind="simulation", seed=0, start="2000-01-01"):
    rng = np.random.default_rng(seed)
    t = pd.date_range(start, periods=n, freq="D")
    q = 5000 + 4000 * np.sin(2 * np.pi * (t.dayofyear - 120) / 365.25) + rng.normal(0, 200, n)
    return pd.DataFrame({"timestamp": t, "latitude": 12.525, "longitude": 105.925, "station_id": "cell",
                         "discharge": np.clip(q, 100, None), "unit": "m3/s", "source": "test", "kind": kind,
                         "retrieved_at_utc": "2026-01-01T00:00:00+00:00", "provenance": "synthetic"})


# ---------- schema ----------
def test_schema_accepts_valid_and_rejects_bad_kind_or_unit():
    df = make_frame()
    assert list(validate_schema(df).columns) == COLUMNS
    with pytest.raises(SchemaError):
        validate_schema(df.assign(kind="gauge"))
    with pytest.raises(SchemaError):
        validate_schema(df.assign(unit="m3/h"))
    with pytest.raises(SchemaError):
        validate_schema(df.drop(columns=["provenance"]))


def test_simulation_and_observation_cannot_be_mixed_silently():
    sim, obs = make_frame(kind="simulation"), make_frame(kind="observation")
    with pytest.raises(MixedKindError):
        combine([sim, obs])
    with pytest.raises(MixedKindError):
        combine([sim, obs], allow_mixed=True)  # a documenting note is also required
    out = combine([sim, obs], allow_mixed=True, note="MRC gauge vs GloFAS cell; different support")
    assert out.attrs["mixed_kind_note"]
    with pytest.raises(MixedKindError):
        single_kind(out)  # models refuse mixed series


# ---------- validation ----------
def test_validation_report_on_clean_series():
    rep = validate_series(make_frame())
    assert rep["continuous_daily"] and rep["kind"] == "simulation" and rep["rows"] == 800


@pytest.mark.parametrize("breaker, match", [
    (lambda d: pd.concat([d, d.iloc[[5]]]).sort_values("timestamp"), "duplicate"),
    (lambda d: d.drop(index=[100, 101]), "missing daily"),
    (lambda d: d.assign(discharge=d.discharge.where(d.index != 3, -5.0)), "negative"),
    (lambda d: d.assign(discharge=d.discharge.where(d.index % 10 != 0)), "missing values exceeds"),
    (lambda d: d.assign(station_id=np.where(d.index < 5, "other", "cell")), "one station"),
])
def test_validation_hard_failures(breaker, match):
    with pytest.raises(DataQualityError, match=match):
        validate_series(breaker(make_frame()))


def test_trim_leading_and_trailing_nans_only():
    d = make_frame(50)
    d.loc[:4, "discharge"] = np.nan
    d.loc[48:, "discharge"] = np.nan
    t = trim_to_valid_span(d)
    assert len(t) == 43 and t.discharge.notna().all()


# ---------- adapters ----------
def _payload(n=5, unit="m³/s", lat=12.525002, lon=105.92502, nulls=2):
    t = [str(x.date()) for x in pd.date_range("1996-12-30", periods=n)]
    v = [None] * nulls + [100.0 + i for i in range(n - nulls)]
    return json.dumps({"latitude": lat, "longitude": lon, "daily_units": {"river_discharge": unit},
                       "daily": {"time": t, "river_discharge": v}}).encode()


def test_glofas_parse_cache_and_no_second_request(tmp_path):
    calls = []

    def fake(url):
        calls.append(url)
        return _payload()

    src = GloFASOpenMeteo(tmp_path, fetch=fake)
    df = src.load()
    assert calls and "models=consolidated_v4" in calls[0] and "latitude=12.525" in calls[0]
    assert (df.kind == "simulation").all() and (df.unit == "m3/s").all()
    assert df.timestamp.iloc[0] == pd.Timestamp("1997-01-01")  # leading nulls trimmed
    assert "simulated, not a gauge" in df.provenance.iloc[0]
    n_before = len(calls)
    GloFASOpenMeteo(tmp_path, fetch=fake).load()
    assert len(calls) == n_before  # second load served from the cache


def test_glofas_rejects_unexpected_unit(tmp_path):
    src = GloFASOpenMeteo(tmp_path, fetch=lambda u: _payload(unit="ft3/s"))
    with pytest.raises(ValueError, match="unit"):
        src.load()


def test_mrc_adapter_refuses_without_authorised_file(tmp_path):
    with pytest.raises(MRCAccessRequired):
        MRCAdapter(None, station_id="KRATIE", latitude=12.48, longitude=106.02).load()
    with pytest.raises(MRCAccessRequired):
        MRCAdapter(tmp_path / "missing.csv", station_id="KRATIE", latitude=12.48, longitude=106.02).load()


def test_mrc_adapter_maps_authorised_export_to_common_schema_as_observation(tmp_path):
    f = tmp_path / "mrc.csv"
    pd.DataFrame({"date": pd.date_range("2010-01-01", periods=30), "discharge": 2000.0,
                  "unit": "m3/s"}).to_csv(f, index=False)
    df = MRCAdapter(f, station_id="KRATIE", latitude=12.48, longitude=106.02, licence_note="test").load()
    assert (df.kind == "observation").all() and single_kind(df) == "observation"
    assert validate_series(df)["kind"] == "observation"
    bad = tmp_path / "bad.csv"
    pd.DataFrame({"date": ["2010-01-01"], "discharge": [1.0], "unit": ["ft3/s"]}).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="unit"):
        MRCAdapter(bad, station_id="K", latitude=0, longitude=0).load()


def test_compact_roundtrip_keeps_schema_and_kind(tmp_path):
    df = make_frame(40)
    save_compact(df, tmp_path / "a.csv", tmp_path / "a.json", {})
    back = load_compact(tmp_path / "a.csv", tmp_path / "a.json")
    assert list(back.columns) == COLUMNS and (back.kind == "simulation").all()
    assert np.allclose(back.discharge, df.discharge)


# ---------- features and chronological splits ----------
def test_features_use_only_past_values():
    lq = ft.log_series(make_frame(400))
    X = ft.feature_frame(lq)
    t = lq.index[200]
    assert X.loc[t, "lag0"] == lq.loc[t] and X.loc[t, "lag7"] == lq.iloc[193]
    assert X.loc[t, "roll_mean7"] == pytest.approx(lq.iloc[194:201].mean())
    changed = lq.copy()
    changed.iloc[201:] += 5.0  # altering the future must not change features at t
    assert ft.feature_frame(changed).loc[t].equals(X.loc[t])


def test_target_is_h_days_ahead_and_segments_are_by_target_date():
    lq = ft.log_series(make_frame(1200))
    X, y, tdates = ft.build_dataset(lq, 7)
    t = X.index[100]
    assert y.loc[t] == lq.loc[t + pd.Timedelta(days=7)]
    seg = ft.segments("2001-12-31", "2002-06-30")
    tr, va, te = (ft.in_segment(tdates, seg[k]) for k in ("train", "val", "test"))
    assert not (tr & va).any() and not (va & te).any() and not (tr & te).any()
    assert tdates[tr].max() <= pd.Timestamp("2001-12-31") and tdates[te].min() > pd.Timestamp("2002-06-30")
    assert tr.any() and va.any() and te.any()
    assert (tr | va | te).all()  # every sample belongs to exactly one segment


# ---------- baselines ----------
def test_persistence_and_seasonal_naive_definitions():
    lq = ft.log_series(make_frame(800))
    o = lq.index[400:405]
    assert np.array_equal(md.persistence(lq, o, 3), lq.loc[o].to_numpy())
    sn = md.seasonal_naive(lq, o, 3)
    assert np.allclose(sn, lq.shift(362).loc[o].to_numpy())
    # the value used lies at (origin + h - 365), i.e. in the past of the origin
    assert (o + pd.Timedelta(days=3) - pd.Timedelta(days=365) <= o).all()
    with pytest.raises(ValueError):
        md.seasonal_naive(lq, o, 400)


def test_climatology_uses_training_data_only_and_is_periodic():
    lq = ft.log_series(make_frame(1500))
    train = lq[:730]
    clim = md.doy_climatology(train)
    assert clim.shape == (366,) and np.isfinite(clim).all()
    o = lq.index[800:803]
    fc = md.climatology_forecast(clim, o, 5)
    assert np.allclose(fc, clim[(o + pd.Timedelta(days=5)).dayofyear.to_numpy() - 1])


# ---------- ARIMA forecasts ----------
def test_vectorised_arima_forecast_matches_statsmodels_forecast():
    rng = np.random.default_rng(3)
    n = 1200
    e = rng.normal(0, 0.1, n)
    a = np.zeros(n)
    for i in range(2, n):
        a[i] = 0.9 * a[i - 1] - 0.1 * a[i - 2] + e[i] + 0.3 * e[i - 1]
    t = pd.date_range("2000-01-01", periods=n)
    lq = pd.Series(8.5 + 1.0 * np.sin(2 * np.pi * t.dayofyear / 365.25) + a, index=t)
    m = md.AnomalyARIMA((2, 0, 1)).fit(lq[:900])
    fc = m.forecast_all(lq, (1, 3, 7))
    anom = m._anomalies(lq)
    for origin in (950, 1100):
        res = ARIMA(anom[: origin + 1], order=(2, 0, 1), trend="n").filter(m.params)
        ref = res.forecast(7)
        for h in (1, 3, 7):
            expected = ref[h - 1] + m.clim[(lq.index[origin] + pd.Timedelta(days=h)).dayofyear - 1]
            assert fc[h].iloc[origin] == pytest.approx(expected, rel=1e-9, abs=1e-9)


def test_arima_forecast_at_origin_ignores_the_future():
    rng = np.random.default_rng(4)
    t = pd.date_range("2000-01-01", periods=1000)
    lq = pd.Series(8 + np.sin(2 * np.pi * t.dayofyear / 365.25) + rng.normal(0, 0.1, 1000).cumsum() * 0.01, index=t)
    m = md.AnomalyARIMA((1, 0, 0)).fit(lq[:600])
    a = m.forecast_all(lq, (3,))[3]
    future_changed = lq.copy()
    future_changed.iloc[701:] += 3.0
    b = m.forecast_all(future_changed, (3,))[3]
    assert a.iloc[700] == pytest.approx(b.iloc[700])


# ---------- metrics ----------
def test_metrics_on_known_values():
    y, p = np.array([10.0, 20.0, 30.0]), np.array([12.0, 18.0, 33.0])
    assert ev.mae(y, p) == pytest.approx((2 + 2 + 3) / 3)
    assert ev.rmse(y, p) == pytest.approx(np.sqrt((4 + 4 + 9) / 3))
    assert ev.nse(y, y) == 1.0
    assert ev.nse(y, np.full(3, y.mean())) == pytest.approx(0.0)


def test_summary_skill_vs_persistence_and_bootstrap_interval():
    rng = np.random.default_rng(0)
    origin = pd.date_range("2020-01-01", periods=300)
    y = 100 + rng.normal(0, 5, 300)
    pers = y + rng.normal(0, 10, 300)
    good = y + rng.normal(0, 2, 300)
    rows = []
    for name, p in (("persistence", pers), ("m", good)):
        rows.append(pd.DataFrame({"model": name, "horizon": 1, "origin": origin,
                                  "target_date": origin + pd.Timedelta(days=1), "y_true": y, "y_pred": p}))
    s = ev.summarise(pd.concat(rows)).set_index("model")
    assert s.loc["persistence", "MAE_skill_vs_persistence"] == pytest.approx(0.0)
    assert s.loc["m", "MAE_skill_vs_persistence"] > 0.5
    lo, hi = ev.block_bootstrap_skill(y, good, pers, block=20, n_boot=200)
    assert lo < s.loc["m", "MAE_skill_vs_persistence"] < hi and lo > 0.3
