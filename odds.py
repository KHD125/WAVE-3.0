"""
alpha.odds — Stage 3 of WAVE 3.0 (see alpha/PLAN.md §4): the probability machine.

For every stock-week: P(wave: +15% in 4w) and P(crash: −15% in 4w), produced
walk-forward — the forecast for week t comes from a model that has never seen
week t, nor any week whose LABEL overlaps t (a 4-week label needs a ≥29-day
embargo, or the training labels themselves contain the future).

The model is a deliberately boring logistic regression (PLAN §4): at ~50k rows
and ~50 weeks, anything fancier is overfitting with better PR. It is judged by
ONE standard — calibration: when it says 30%, reality must deliver ~30%.

Feature set locked by the T1/T2 ledger tests (2026-08-23):
    scan (10)  p_range_pos p_from_high p_ret_7d p_ret_30d p_ret_6m
               p_rvol p_vol_trend p_px_sma50 p_px_sma200 p_log_mcap
    track (3)  persist       (T1: in — 0.81 overlap with range_pos, modest add)
               sector_heat   (T2: in — IC .098@8w at only .36 overlap; flagged
                              better-than-predicted, mechanism = industry momentum)
               sector_breadth
    excluded   wave_age (persist's twin) · trend_4w (noise) · sector_heat_d4 (dead)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

WAVE_PCT = 15.0                # +15% in 4 weeks = a wave (PLAN §5)
CRASH_PCT = -15.0
LABEL_COL = "fwd_ret_4w"
EMBARGO_DAYS = 29              # label horizon + 1 day; Law: no label overlap, ever
MIN_TRAIN_WEEKS = 26

MODEL_FEATURES = [
    "p_range_pos", "p_from_high", "p_ret_7d", "p_ret_30d", "p_ret_6m",
    "p_rvol", "p_vol_trend", "p_px_sma50", "p_px_sma200", "p_log_mcap",
    "persist", "sector_heat", "sector_breadth",
]


def _label(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    panel["y_up"] = (panel[LABEL_COL] >= WAVE_PCT).astype(float)
    panel["y_dn"] = (panel[LABEL_COL] <= CRASH_PCT).astype(float)
    panel.loc[panel[LABEL_COL].isna(), ["y_up", "y_dn"]] = np.nan
    return panel


def _clean(panel: pd.DataFrame) -> pd.DataFrame:
    ok = (panel["in_universe"].fillna(False).astype(bool)
          & ~panel["is_corporate_action"].fillna(False).astype(bool))
    return panel[ok].dropna(subset=MODEL_FEATURES)


def training_mask(dates: pd.Series, forecast_date: pd.Timestamp) -> pd.Series:
    """Rows legal to train on when forecasting `forecast_date`.

    date ≤ forecast − EMBARGO_DAYS, so every training label (which looks 4 weeks
    past its own date) is fully realized BEFORE the forecast week begins. This
    function exists so a test can pin it — the no-leakage contract lives here."""
    return dates <= (forecast_date - pd.Timedelta(days=EMBARGO_DAYS))


def fit_predict_one(train: pd.DataFrame, week: pd.DataFrame) -> pd.DataFrame:
    """Fit up/down models on `train`, return week + p_up/p_dn."""
    sc = StandardScaler().fit(train[MODEL_FEATURES])
    out = week.copy()
    for tgt, col in (("y_up", "p_up"), ("y_dn", "p_dn")):
        t = train.dropna(subset=[tgt])
        if t[tgt].nunique() < 2:
            out[col] = t[tgt].mean() if len(t) else np.nan   # degenerate: base rate
            continue
        m = LogisticRegression(max_iter=2000, C=1.0)
        m.fit(sc.transform(t[MODEL_FEATURES]), t[tgt])
        out[col] = m.predict_proba(sc.transform(week[MODEL_FEATURES]))[:, 1]
    out["net_edge"] = out["p_up"] - out["p_dn"]
    return out


def walk_forward(panel: pd.DataFrame) -> pd.DataFrame:
    """Out-of-sample probabilities for every week with ≥MIN_TRAIN_WEEKS of clean
    pre-embargo history. Nothing in a row's forecast postdates the row (Law 9's
    precondition: a log is only unbribable if the forecasts were, too)."""
    d = _label(_clean(panel))
    dates = sorted(d["date"].unique())
    outs = []
    for t in dates:
        tr = d[training_mask(d["date"], t)].dropna(subset=["y_up"])
        if tr["date"].nunique() < MIN_TRAIN_WEEKS:
            continue
        outs.append(fit_predict_one(tr, d[d["date"] == t]))
    if not outs:
        return pd.DataFrame()
    return pd.concat(outs, ignore_index=True)


def brier_score(oos: pd.DataFrame, prob_col: str = "p_up",
                label_col: str = "y_up") -> float:
    """Mean squared error of stated probability vs outcome — the single-number
    honesty gauge (0 = oracle; predicting the base rate every time scores
    base*(1-base), ≈0.132 at a 15.7% base). Supplements the decile table, never
    replaces it: Brier blends calibration and discrimination into one figure."""
    d = oos.dropna(subset=[prob_col, label_col])
    return float(np.mean((d[prob_col] - d[label_col]) ** 2))


def calibration_table(oos: pd.DataFrame, prob_col: str = "p_up",
                      label_col: str = "y_up", bins: int = 10) -> pd.DataFrame:
    """Stated probability vs realized frequency, by decile of stated probability.
    The judge (PLAN §1): |stated − actual| beyond ~5pp per decile = dishonest model."""
    d = oos.dropna(subset=[prob_col, label_col]).copy()
    d["bucket"] = pd.qcut(d[prob_col].rank(method="first"), bins, labels=False) + 1
    g = d.groupby("bucket").agg(
        n=(label_col, "size"),
        stated=(prob_col, "mean"),
        actual=(label_col, "mean"),
        fwd_4w=(LABEL_COL, "mean"),
    ).reset_index()
    g["gap_pp"] = (g["actual"] - g["stated"]) * 100.0
    return g


if __name__ == "__main__":
    from alpha.scan import compute_features
    from alpha.track import compute_track

    panel = compute_track(compute_features(pd.read_parquet("alpha/_panel_long.parquet")))
    oos = walk_forward(panel)
    wk = oos["date"].nunique()
    print(f"walk-forward out-of-sample: {len(oos):,} rows over {wk} weeks "
          f"({oos['date'].min():%Y-%m-%d} -> {oos['date'].max():%Y-%m-%d})")
    print(f"base rates  wave {oos['y_up'].mean()*100:.2f}%   crash {oos['y_dn'].mean()*100:.2f}%")
    print()
    for col, lab, name in (("p_up", "y_up", "WAVE"), ("p_dn", "y_dn", "CRASH")):
        t = calibration_table(oos, col, lab)
        print(f"CALIBRATION — P({name})   (stated vs actual, out-of-sample only)")
        print(t.to_string(index=False, float_format=lambda v: f"{v:8.3f}"))
        print()
    top = oos[oos["p_up"] >= oos.groupby("date")["p_up"].transform(lambda s: s.quantile(0.9))]
    print("TOP DECILE BY P(WAVE), per week, out-of-sample:")
    print(f"  stated {top['p_up'].mean()*100:5.1f}%   actual {top['y_up'].mean()*100:5.1f}%   "
          f"base {oos['y_up'].mean()*100:.1f}%   lift {top['y_up'].mean()/oos['y_up'].mean():.2f}x")
    print(f"  crash rate in the same names: {top['y_dn'].mean()*100:.1f}% "
          f"(base {oos['y_dn'].mean()*100:.1f}%)  <- Law 8 check: waves break both ways")
