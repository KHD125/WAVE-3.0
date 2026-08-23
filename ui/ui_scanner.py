"""
ui.ui_scanner — Tab 2. Deep Scanner: the hunt.

This module is the deliberate STATEFUL counterpart to the stateless tear sheet
(PRISM convention). It OWNS the filter cascade and its `sc_*` session_state keys.
Do not harmonize the two files — the split is the point.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from ui.ui_components import download, prob_table


def render(ctx: dict) -> None:
    scored, meta = ctx["scored"], ctx["meta"]
    week = scored[scored["date"] == meta["latest"]].copy()

    st.subheader("Deep Scanner")
    st.caption(f"Every investable stock in the {meta['latest']:%d %b %Y} snapshot, with its "
               "modelled odds. Filter, sort, export — then send a ticker to the Tear Sheet.")

    c1, c2, c3 = st.columns([2, 1, 1])
    sectors = sorted(week["sector"].dropna().unique())
    pick = c1.multiselect("Sector", sectors, key="sc_sectors")
    cats = sorted(week["category"].dropna().unique())
    cat = c2.multiselect("Category", cats, default=[], key="sc_cats")
    min_edge = c3.slider("Min net edge (pp)", -10.0, 20.0, 0.0, 0.5, key="sc_edge")

    c4, c5, c6 = st.columns(3)
    min_up = c4.slider("Min P(wave) %", 0.0, 40.0, 0.0, 0.5, key="sc_up")
    max_dn = c5.slider("Max P(crash) %", 0.0, 40.0, 40.0, 0.5, key="sc_dn")
    min_persist = c6.slider("Min persistence (weeks)", 0, 52, 0, key="sc_persist")

    f = week
    if pick:
        f = f[f["sector"].isin(pick)]
    if cat:
        f = f[f["category"].isin(cat)]
    f = f[(f["net_edge"] * 100 >= min_edge) & (f["p_up"] * 100 >= min_up)
          & (f["p_dn"] * 100 <= max_dn) & (f["persist"] >= min_persist)]
    f = f.sort_values("net_edge", ascending=False)

    st.caption(f"**{len(f):,}** of {len(week):,} stocks pass · "
               f"median P(wave) {f['p_up'].median():.1%} vs universe {week['p_up'].median():.1%}"
               if len(f) else "No stocks match these filters.")
    if len(f):
        prob_table(f.head(200), height=560)
        download(f, "⬇️ Download filtered scan",
                 f"wave3_scan_{meta['latest']:%Y-%m-%d}.csv")
        st.caption("Showing the top 200 by net edge. Download for the full filtered set.")
