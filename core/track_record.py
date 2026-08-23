"""
core.track_record — grade the frozen forecasts against what actually happened.

This closes the loop the legacy system never had. Wave Detection published
`breakout_score: 'probability of price breakout'` for three versions and no code
ever counted a breakout. Here, every forecast that has aged past its horizon is
joined to its realized outcome and scored.

TWO SOURCES, AND THE DIFFERENCE MATTERS:

  grade_log()        the LIVE record — forecasts frozen in logs/waves_log.csv
                     BEFORE their outcome existed. This is evidence.
  backtest_record()  a walk-forward re-run over history. This is a BACKTEST:
                     useful while the log is young, but it was computed with
                     today's code on data that already happened, so it can never
                     be as strong as the frozen log.

`summary()` prefers the live record and falls back to the backtest, and always
reports WHICH — a track record that quietly substitutes a backtest for live
evidence is exactly the substitution this project exists to prevent.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd

from .config import LABEL_HORIZON_WEEKS, WAVE_PCT

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(_ROOT, "logs", "waves_log.csv")


def load_log(path: str = LOG) -> pd.DataFrame:
    """Read the frozen forecast log. Empty frame if it does not exist yet."""
    if not os.path.exists(path):
        return pd.DataFrame()
    log = pd.read_csv(path)
    for col in ("snapshot_date", "trained_through"):
        if col in log.columns:
            log[col] = pd.to_datetime(log[col], errors="coerce")
    return log


def grade_log(panel: pd.DataFrame, log: Optional[pd.DataFrame] = None,
              path: str = LOG) -> pd.DataFrame:
    """Join each frozen forecast to its realized outcome.

    Only rows whose horizon has fully elapsed are graded; a forecast still in
    flight is neither a hit nor a miss and must not be counted as either.
    """
    log = load_log(path) if log is None else log
    if log.empty or "snapshot_date" not in log.columns:
        return pd.DataFrame()

    label = f"fwd_ret_{LABEL_HORIZON_WEEKS}w"
    if label not in panel.columns:
        return pd.DataFrame()

    truth = panel[["ticker", "date", label]].rename(columns={"date": "snapshot_date"})
    graded = log.merge(truth, on=["ticker", "snapshot_date"], how="left")
    graded = graded[graded[label].notna()].copy()
    if graded.empty:
        return graded
    graded["hit"] = (graded[label] >= WAVE_PCT).astype(float)
    return graded


# What the log STATED as its probability. v3.0 wrote a fitted `p_up`; v3.1 writes
# `hist_rate`, the counted historical wave rate of the row's decile. Grading asks
# the same question of both — did the stated number match what happened — so the
# column is looked up, never assumed. Assuming it is how `summary` came to read a
# `p_up` that v3.1 stopped writing: it would have raised KeyError on the 30th
# graded row, i.e. the exact moment the app first had real evidence to show.
_STATED_CANDIDATES = ("hist_rate", "p_up")


def _stated_col(df: pd.DataFrame) -> Optional[str]:
    return next((c for c in _STATED_CANDIDATES if c in df.columns), None)


def _stats(df: pd.DataFrame, prob_col: str, hit_col: str, base: float,
           source: str) -> dict:
    stated = float(df[prob_col].mean())
    actual = float(df[hit_col].mean())
    return {
        "source": source,
        "n": int(len(df)),
        "weeks": int(df["snapshot_date"].nunique()) if "snapshot_date" in df else
                 int(df["date"].nunique()),
        "stated": stated,
        "actual": actual,
        "gap_pp": (actual - stated) * 100.0,
        "base": base,
        "lift": actual / base if base else np.nan,
    }


def backtest_record(oos: pd.DataFrame) -> dict:
    """Track record from a walk-forward re-run (weaker evidence than the log)."""
    if oos.empty:
        return {}
    base = float(oos["y_up"].mean())
    top = oos[oos["p_up"] >= oos.groupby("date")["p_up"].transform(
        lambda s: s.quantile(0.9))]
    if top.empty:
        return {}
    return _stats(top.rename(columns={"y_up": "hit"}), "p_up", "hit", base,
                  source="backtest")


def summary(panel: pd.DataFrame, oos: Optional[pd.DataFrame] = None,
            path: str = LOG) -> Optional[dict]:
    """The Summary tab's headline. Live record if it exists, else backtest, else None.

    ALWAYS carries `source`, so the UI can label which one the reader is seeing.
    """
    graded = grade_log(panel, path=path)
    stated = _stated_col(graded) if not graded.empty else None
    if stated and len(graded) >= 30:
        base = float((panel[f"fwd_ret_{LABEL_HORIZON_WEEKS}w"] >= WAVE_PCT).mean())
        return _stats(graded, stated, "hit", base, source="live log")
    if oos is not None and not oos.empty:
        rec = backtest_record(oos)
        if rec:
            rec["pending"] = int(len(load_log(path)) - len(graded))
            return rec
    return None
