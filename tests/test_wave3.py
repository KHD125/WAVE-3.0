"""
Contract tests for WAVE 3.0 stages (alpha/scan.py, track.py, odds.py, weekly.py).

Each pins a Law from alpha/PLAN.md §2. The one that matters most is the no-leakage
contract on odds.training_mask — a probability system that peeks is worse than the
42 unmeasured patterns it replaced, because it looks calibrated while lying.
"""

import os

import numpy as np
import pandas as pd
import pytest

from core.odds import EMBARGO_DAYS, calibration_table, training_mask
from core.scan import FEATURES, compute_features
from core.track import _past_date_map, _run_length


def _mini_panel():
    """3 tickers x 3 weeks with everything scan needs."""
    rows = []
    for dt in ("2026-01-04", "2026-01-11", "2026-01-18"):
        for i, tk in enumerate(("AAA", "BBB", "CCC")):
            rows.append(dict(
                ticker=tk, date=pd.Timestamp(dt), price=100.0 + 10 * i,
                low_52w=50.0, high_52w=200.0, from_high_pct=-10.0 - i,
                ret_7d=1.0 * i, ret_30d=2.0 * i, ret_6m=3.0 * i, rvol=1.0 + i,
                volume_30d=1e6, volume_90d=1e6, sma_50d=95.0, sma_200d=90.0,
                market_cap=1e10 * (i + 1), in_universe=True, sector="S1",
            ))
    return pd.DataFrame(rows)


# ── scan: percentiles are within-week and universe-only (Law 2) ───────────────

def test_scan_percentiles_are_within_week_and_bounded():
    out = compute_features(_mini_panel())
    for f in FEATURES:
        col = out[f"p_{f}"]
        assert col.between(0, 1).all(), f"p_{f} out of [0,1]"
    one_week = out[out["date"] == "2026-01-04"]
    # 3 distinct prices -> ranks must be 1/3, 2/3, 3/3 within the week
    assert sorted(one_week["p_px_sma200"].round(4)) == [round(1/3, 4), round(2/3, 4), 1.0]


def test_scan_excludes_non_universe_rows_from_ranking():
    p = _mini_panel()
    p.loc[p["ticker"] == "CCC", "in_universe"] = False
    out = compute_features(p)
    ccc = out[out["ticker"] == "CCC"]
    assert ccc[[f"p_{f}" for f in FEATURES]].isna().all().all(), \
        "non-universe rows must never be ranked"
    week = out[(out["date"] == "2026-01-04") & out["in_universe"]]
    assert week["p_log_mcap"].max() == 1.0, "remaining rows re-rank to a full 0-1 scale"


# ── track: streaks and calendar lookback (Law 3) ──────────────────────────────

def test_run_length_counts_consecutive_true_within_ticker():
    flag = pd.Series([True, True, False, True, True, True])
    by = pd.Series(["A", "A", "A", "A", "B", "B"])
    # A: streak 1,2 then reset, then 1 again; B: fresh count despite adjacent True
    assert _run_length(flag, by).tolist() == [1, 2, 0, 1, 1, 2]


def test_past_date_map_is_calendar_not_index():
    # Weekly dates with an 8-day gap: 4 snapshots back is NOT 28 days back.
    dates = pd.Index(pd.to_datetime(
        ["2026-01-04", "2026-01-12", "2026-01-19", "2026-01-26", "2026-02-02"]))
    m = _past_date_map(dates, days=28, tol=4)
    # 2026-02-02 - 28d = 2026-01-05; nearest is 2026-01-04 (1 day off) — legal.
    assert m[pd.Timestamp("2026-02-02")] == pd.Timestamp("2026-01-04")
    # Earliest date has no past within tolerance.
    assert pd.isna(m[pd.Timestamp("2026-01-04")])


# ── odds: THE no-leakage contract ─────────────────────────────────────────────

def test_training_mask_embargoes_label_overlap():
    dates = pd.Series(pd.to_datetime(
        ["2026-01-04", "2026-01-25", "2026-02-01", "2026-02-22", "2026-03-01"]))
    forecast = pd.Timestamp("2026-03-01")
    legal = dates[training_mask(dates, forecast)]
    # A 4-week label from 2026-02-22 resolves on 2026-03-22 — AFTER the forecast
    # date. Training on it would smuggle the future into the model.
    assert pd.Timestamp("2026-02-22") not in set(legal)
    assert pd.Timestamp("2026-03-01") not in set(legal)
    assert pd.Timestamp("2026-01-25") in set(legal)
    # The boundary itself: anything younger than EMBARGO_DAYS is excluded.
    assert (forecast - legal.max()).days >= EMBARGO_DAYS


def test_calibration_table_shape_and_honesty_columns():
    n = 1000
    rng = np.random.default_rng(7)
    p = rng.uniform(0, 1, n)
    oos = pd.DataFrame({
        "p_up": p,
        "y_up": (rng.uniform(0, 1, n) < p).astype(float),   # perfectly calibrated
        "fwd_ret_4w": rng.normal(0, 5, n),
    })
    t = calibration_table(oos)
    assert len(t) == 10 and t["n"].sum() == n
    # Perfect calibration -> every decile gap within a few points.
    assert t["gap_pp"].abs().max() < 8.0


# ── weekly: the log is append-only (Law 9) ────────────────────────────────────

def test_append_log_never_truncates(tmp_path, monkeypatch):
    import core.decide as weekly
    monkeypatch.setattr(weekly, "LOG", str(tmp_path / "waves_log.csv"))
    row = pd.DataFrame([{
        "logged_at_utc": "2026-08-23T00:00:00+00:00", "model_version": "3.0",
        "snapshot_date": pd.Timestamp("2026-08-16"),
        "trained_through": pd.Timestamp("2026-07-19"),
        "ticker": "AAA", "sector": "S1", "price": 100.0,
        "p_up": 0.2, "p_dn": 0.05, "net_edge": 0.15,
        "persist": 3, "sector_heat": 0.6, "p_range_pos": 0.9,
    }])
    weekly.append_log(row)
    weekly.append_log(row.assign(ticker="BBB"))
    back = pd.read_csv(weekly.LOG)
    assert len(back) == 2 and set(back["ticker"]) == {"AAA", "BBB"}, \
        "a second append must extend the log, never rewrite it"
