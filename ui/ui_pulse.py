"""
ui.ui_pulse — Tab 4. Market Pulse: sector rotation and breadth.

Content is restricted to what measured positive. `sector_heat` earned this tab:
IC +0.098 @ 8w at only 0.36 overlap with range_pos (ledger #52) — the strongest
orthogonal signal in the project. `sector_heat_d4` was tested and is dead
(+0.005 IC), so rotation *velocity* is deliberately NOT shown: a chart nobody
can act on is how the old app grew 33 surfaces.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from core.config import MAX_PER_SECTOR
from ui.ui_components import stat_strip


def render(ctx: dict) -> None:
    scored, meta = ctx["scored"], ctx["meta"]
    week = scored[scored["date"] == meta["latest"]]

    st.subheader("Sector rotation")
    st.caption("Sector heat = the sector's average position-in-52w-range percentile. "
               "Breadth = share of its members in the top tercile — breadth is the "
               "honest one, since a single outlier can drag an average up.")

    g = (week.groupby("sector")
              .agg(stocks=("ticker", "size"), heat=("sector_heat", "first"),
                   breadth=("sector_breadth", "first"), p_wave=("p_up", "mean"),
                   p_crash=("p_dn", "mean"), edge=("net_edge", "mean"))
              .reset_index())
    g = g[g["stocks"] >= 3].sort_values("heat", ascending=False)

    hot, cold = g.head(1), g.tail(1)
    stat_strip([
        ("Hottest sector", hot["sector"].iloc[0], f"heat {hot['heat'].iloc[0]:.2f}", "good"),
        ("Coldest sector", cold["sector"].iloc[0], f"heat {cold['heat'].iloc[0]:.2f}", "bad"),
        ("Universe in wave zone", f"{(week['p_range_pos'] >= 0.8).mean():.0%}",
         "top 20% of their 52w range", ""),
        ("Sector cap", f"{MAX_PER_SECTOR}/sector", "the seatbelt — never tuned", "warn"),
    ])

    view = g.rename(columns={"sector": "Sector", "stocks": "Stocks", "heat": "Heat",
                             "breadth": "Breadth", "p_wave": "Avg P(wave)",
                             "p_crash": "Avg P(crash)", "edge": "Avg edge"})
    st.dataframe(
        view.style.format({"Heat": "{:.2f}", "Breadth": "{:.0%}", "Avg P(wave)": "{:.1%}",
                           "Avg P(crash)": "{:.1%}", "Avg edge": "{:+.1%}"})
            .background_gradient(subset=["Heat"], cmap="RdYlGn")
            .background_gradient(subset=["Breadth"], cmap="RdYlGn"),
        use_container_width=True, hide_index=True, height=min(38 * (len(view) + 1), 620))

    st.info(f"**Why the cap stays at {MAX_PER_SECTOR}.** Loosening it raised backtested alpha "
            "monotonically (2/sector +1.5%/yr → uncapped +11.7%/yr) — because it becomes a "
            "sector bet. That is also the trade that produces India's −70%, 65-month-recovery "
            "momentum crashes. Rotation is ridden through the probabilities; the cap is the "
            "seatbelt.", icon="🔒")
