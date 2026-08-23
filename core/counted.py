"""
core.counted — Stage 3 of WAVE 3.1: the odds, COUNTED not fitted.

THE DISTINCTION THIS MODULE EXISTS TO ENFORCE:

    fitted    "this stock has a 19% chance"       a claim about the future.
                                                  v3.0 tried it; miscalibrated by 16pp.
    counted   "of 16,769 past stock-weeks in      a count of your own data.
               this decile, 18.6% waved"          cannot be miscalibrated, because
                                                  nothing was fitted.

Wave Detection published `breakout_score: 'probability of price breakout'` for three
versions and no code ever counted a breakout. This module is the counting.

HONEST LIMIT, stated rather than hidden: rates are computed over the same archive used
to choose `range_pos` as the ranker. They are facts about the past, not an escape from
the sample. Only the frozen forward log escapes it.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .config import LABEL_HORIZON_WEEKS, N_BINS, RANK_FEATURE

LABEL_COL = f"fwd_ret_{LABEL_HORIZON_WEEKS}w"


def decile_table(scored: pd.DataFrame, feature: str = RANK_FEATURE,
                 label: str = "y_up", bins: int = N_BINS) -> pd.DataFrame:
    """Historical hit rate per feature decile, with the sample size behind each.

    `n` is returned deliberately: a 40% rate on 12 observations is not a finding, and
    the caller must be able to see the difference without asking.
    """
    d = scored[[feature, label]].dropna()
    if len(d) < bins * 30:
        return pd.DataFrame()
    # rank(method="first") before qcut: identical percentile values are common and
    # would otherwise collapse bin edges, silently producing fewer bins than asked.
    d = d.assign(_bin=pd.qcut(d[feature].rank(method="first"), bins,
                              labels=False, duplicates="drop") + 1)
    base = float(d[label].mean())
    out = (d.groupby("_bin")
             .agg(n=(label, "size"), lo=(feature, "min"), hi=(feature, "max"),
                  rate=(label, "mean"))
             .reset_index()
             .rename(columns={"_bin": "decile"}))
    out["base"] = base
    out["lift"] = np.where(base > 0.0, out["rate"] / base, np.nan)
    return out


def attach_counted_odds(week: pd.DataFrame, scored: pd.DataFrame,
                        feature: str = RANK_FEATURE, bins: int = N_BINS,
                        label: str = "y_up") -> pd.DataFrame:
    """Give every row in `week` the historical hit rate of its decile.

    Adds: hist_rate · hist_n · hist_lift · hist_base · decile.
    Rows whose feature is missing get NaN — never a filled-in average, which would
    quietly present "no information" as "average odds".
    """
    week = week.copy()
    table = decile_table(scored, feature, label, bins)
    for col in ("decile", "hist_rate", "hist_n", "hist_lift", "hist_base"):
        week[col] = np.nan
    if table.empty:
        return week

    # Bin the live week against the HISTORICAL edges, so a stock's decile means the
    # same thing every week. Re-ranking within the current week would make the label
    # drift with whatever happens to be listed today.
    edges = [-np.inf] + table["hi"].tolist()[:-1] + [np.inf]
    valid = week[feature].notna()
    week.loc[valid, "decile"] = pd.cut(week.loc[valid, feature], bins=edges,
                                       labels=False, duplicates="drop") + 1
    lookup = table.set_index("decile")
    for src, dst in (("rate", "hist_rate"), ("n", "hist_n"),
                     ("lift", "hist_lift"), ("base", "hist_base")):
        week[dst] = week["decile"].map(lookup[src])
    return week


def summarise(table: pd.DataFrame) -> Optional[dict]:
    """Headline for the UI: how strong at the top, and what shape overall?

    MEASURED SHAPE IS A U, NOT A RAMP (ledger #58): decile 1 lifts 1.04x, the
    minimum sits at decile 5 (0.77x), decile 10 peaks at 1.24x. Extremes carry the
    signal; the middle is dead. Wave Detection's position_score docstring asserted
    exactly this ("Extremes matter, middle doesn't") and never counted it.

    So `monotonicity` is reported but is NOT the health check — a clean ramp would
    actually be the surprise. The health check is `top_lift`, and `u_shape` records
    whether both extremes beat the trough, which is the pattern to watch decay.

    It is also why a logistic regression underperformed: fitting a monotone
    relationship to a U-shaped truth cannot work, and counting assumes nothing.
    """
    if table.empty:
        return None
    from scipy.stats import spearmanr
    rho = spearmanr(table["decile"], table["rate"]).correlation
    top = table.iloc[-1]
    trough = float(table["rate"].min())
    return {
        "monotonicity": float(rho),
        "u_shape": bool(table["rate"].iloc[0] > trough and table["rate"].iloc[-1] > trough),
        "trough_decile": int(table.loc[table["rate"].idxmin(), "decile"]),
        "top_rate": float(top["rate"]),
        "top_lift": float(top["lift"]),
        "top_n": int(top["n"]),
        "base": float(table["base"].iloc[0]),
        "n_total": int(table["n"].sum()),
    }
