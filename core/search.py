"""
core.search — find a stock by ticker or company name.

The relevance ladder is lifted from Wave Detection's SearchEngine, which had the
right idea (exact > prefix > contains). The implementation is not: that one ran
`df['company_name'].apply(word_starts_with)` — a Python loop over 2,100 rows on
every keystroke — plus a `drop_duplicates()` across ~700 columns to dedupe rows
already unique by ticker. This is the same ladder, vectorized.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EXACT_TICKER = 100
TICKER_PREFIX = 50
NAME_PREFIX = 30
CONTAINS = 1


def search(df: pd.DataFrame, query: str, tie_break: str = "net_edge") -> pd.DataFrame:
    """Rows matching `query`, most relevant first.

    Ties break on `tie_break` (default net_edge — the number that gets checked,
    not a composite score that never could be).
    """
    q = (query or "").strip().upper()
    if not q or df.empty:
        return df.iloc[0:0]

    tick = df["ticker"].astype(str).str.upper()
    name = df.get("company_name", pd.Series("", index=df.index)).astype(str).str.upper()

    relevance = (
        tick.eq(q) * EXACT_TICKER
        + tick.str.startswith(q) * TICKER_PREFIX
        + name.str.startswith(q) * NAME_PREFIX
        # regex=False: tickers legitimately contain '.', '&', '-' and a user typing
        # "L&T" must not have it read as a pattern.
        + (tick.str.contains(q, regex=False, na=False)
           | name.str.contains(q, regex=False, na=False)) * CONTAINS
    )
    hits = df[relevance > 0].copy()
    if hits.empty:
        return hits
    hits["_relevance"] = relevance[relevance > 0]
    sort_cols = ["_relevance"] + ([tie_break] if tie_break in hits.columns else [])
    return hits.sort_values(sort_cols, ascending=False).drop(columns="_relevance")


def screen_hit_rate(scored: pd.DataFrame, mask: pd.Series,
                    label_col: str = "y_up") -> dict:
    """How often did stocks matching `mask` actually produce a wave?

    THE point of a probability system: a screen can be checked against history,
    because every row carries what happened next. A score-based scanner cannot do
    this — a score has no base rate.

    Returns observation counts alongside the rate. A 40% hit rate on n=12 is not
    a discovery, and the caller must be able to see that.
    """
    d = scored[scored[label_col].notna()]
    if d.empty:
        return {"n": 0, "rate": np.nan, "base": np.nan, "lift": np.nan, "weeks": 0}
    sel = d[mask.reindex(d.index, fill_value=False)]
    base = float(d[label_col].mean())
    if len(sel) < 30:
        return {"n": len(sel), "rate": np.nan, "base": base, "lift": np.nan,
                "weeks": int(sel["date"].nunique()) if len(sel) else 0}
    rate = float(sel[label_col].mean())
    return {"n": len(sel), "rate": rate, "base": base,
            "lift": rate / base if base else np.nan,
            "weeks": int(sel["date"].nunique())}
