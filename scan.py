"""
alpha.scan — Stage 1 of WAVE 3.0 (see alpha/PLAN.md §4).

Ten clean features per stock per week, each converted to a WITHIN-WEEK percentile
across the investable universe. No scores, no patterns, no opinions — measurements
only. Percentiles (Law 2) mean nothing here can go stale when the market drifts:
a 0.90 always means "top decile of this week's universe", in any regime.

Raw feature units (before percentiling):
    range_pos   (price − low_52w) / (high_52w − low_52w)     the audit's one survivor
    from_high   from_high_pct (≤ 0 below the high)           same family, model input
    ret_7d/30d/6m                                            direction context (Law 8:
                                                             raw momentum flags movers,
                                                             not winners — the model may
                                                             still use it conditionally)
    rvol        volume_1d / volume_90d                       wave-energy (both directions)
    vol_trend   volume_30d / volume_90d                      CORRECT units — a ratio near
                                                             1.0 is neutral; the legacy
                                                             system misread the source's
                                                             0-centred vol_ratio columns
    px_sma50, px_sma200                                      trend context
    log_mcap    log(market_cap)                              size carrier
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Feature registry: name -> builder(panel) returning a raw (un-percentiled) Series.
# Banned by PLAN §4: pattern flags, market states, composites — anything with an opinion.
FEATURES = (
    "range_pos", "from_high", "ret_7d", "ret_30d", "ret_6m",
    "rvol", "vol_trend", "px_sma50", "px_sma200", "log_mcap",
)


def _raw_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute the raw feature columns. NaN-honest: no fills, ever (Law 1 heritage)."""
    out = pd.DataFrame(index=panel.index)
    rng = panel["high_52w"] - panel["low_52w"]
    out["range_pos"] = np.where(rng > 0, (panel["price"] - panel["low_52w"]) / rng, np.nan)
    out["from_high"] = panel["from_high_pct"]
    out["ret_7d"] = panel["ret_7d"]
    out["ret_30d"] = panel["ret_30d"]
    out["ret_6m"] = panel["ret_6m"]
    out["rvol"] = panel["rvol"]
    out["vol_trend"] = np.where(panel["volume_90d"] > 0,
                                panel["volume_30d"] / panel["volume_90d"], np.nan)
    out["px_sma50"] = np.where(panel["sma_50d"] > 0, panel["price"] / panel["sma_50d"], np.nan)
    out["px_sma200"] = np.where(panel["sma_200d"] > 0, panel["price"] / panel["sma_200d"], np.nan)
    out["log_mcap"] = np.log(panel["market_cap"].where(panel["market_cap"] > 0))
    return out


def compute_features(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Attach `p_<feature>` percentile columns (0–1, within week, investable rows only).

    Percentiles are computed across `in_universe` rows for each date; rows outside
    the universe get NaN — they are never ranked and never rank others. This keeps
    every model input meaningful as "position within what you could actually buy".
    """
    panel = panel.copy()
    raw = _raw_features(panel)
    for f in FEATURES:
        panel[f"raw_{f}"] = raw[f]

    investable = panel["in_universe"].fillna(False).astype(bool)
    for f in FEATURES:
        col = pd.Series(np.nan, index=panel.index)
        sub = panel.loc[investable, ["date"]].assign(v=raw.loc[investable, f])
        col.loc[investable] = sub.groupby("date")["v"].rank(pct=True)
        panel[f"p_{f}"] = col
    return panel


def feature_columns() -> list:
    """The percentile column names Stage 3 consumes."""
    return [f"p_{f}" for f in FEATURES]
