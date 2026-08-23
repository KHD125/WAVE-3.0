"""
ui.ui_tearsheet — Tab 3. One stock, in depth.

STATELESS BY CONTRACT (PRISM's rule, pinned by tests/test_ui_contract.py):
no st.button / st.slider / st.selectbox / session_state writes anywhere in this
module. `app.py` owns which ticker is selected; this file only renders what it
is handed. The stateful counterpart is ui_scanner.py — do not harmonize them.

Inverted pyramid, same as PRISM's tear sheet:
    Layer 1  the verdict band — the odds, immediately
    Layer 2  WHY — which features push this stock's probability up or down
    Layer 3  evidence — trajectory, streak, sector context, raw data
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from core.config import CRASH_PCT, LABEL_HORIZON_WEEKS, WAVE_PCT
from core.odds import MODEL_FEATURES
from ui.ui_components import stat_strip

_PRETTY = {
    "p_range_pos": "Position in 52w range", "p_from_high": "Nearness to 52w high",
    "p_ret_7d": "1-week return", "p_ret_30d": "1-month return", "p_ret_6m": "6-month return",
    "p_rvol": "Relative volume", "p_vol_trend": "Volume trend (30d vs 90d)",
    "p_px_sma50": "Price vs 50d avg", "p_px_sma200": "Price vs 200d avg",
    "p_log_mcap": "Size (market cap)", "persist": "Weeks held in top tercile",
    "sector_heat": "Sector heat", "sector_breadth": "Sector breadth",
}


def render(ctx: dict, ticker: str) -> None:
    scored, meta = ctx["scored"], ctx["meta"]
    week = scored[scored["date"] == meta["latest"]]
    row = week[week["ticker"] == ticker]
    if row.empty:
        st.info(f"**{ticker}** is not in the investable universe for this snapshot "
                "(it may have failed the price / market-cap / turnover screen).")
        return
    r = row.iloc[0]

    # ── Layer 1: the verdict ──────────────────────────────────────────────
    st.subheader(f"{r['ticker']} — {r.get('company_name', '')}")
    st.caption(f"{r.get('sector', '—')} · {r.get('category', '—')} · ₹{r['price']:,.0f}")
    edge = r["net_edge"]
    stat_strip([
        (f"P(wave ≥ +{WAVE_PCT:.0f}%)", f"{r['p_up']:.1%}",
         f"next {LABEL_HORIZON_WEEKS} weeks · base {meta['base_up']:.1%}", "good"),
        (f"P(crash ≤ {CRASH_PCT:.0f}%)", f"{r['p_dn']:.1%}",
         f"base {meta['base_dn']:.1%}", "bad"),
        ("Net edge", f"{edge:+.1%}", "P(wave) − P(crash)",
         "good" if edge > 0 else "bad"),
        ("Persistence", f"{int(r['persist'])} wk",
         "consecutive weeks in the top tercile", ""),
    ])

    # ── Layer 2: why ──────────────────────────────────────────────────────
    st.markdown("##### Why these odds")
    st.caption("Each feature's percentile for this stock against the investable universe. "
               "Above 0.5 = stronger than the median stock this week. These are the exact "
               "13 inputs the model sees — nothing hidden, nothing extra.")
    feats = []
    for f in MODEL_FEATURES:
        v = r.get(f)
        if pd.isna(v):
            continue
        pct = float(v) if f.startswith("p_") or f in ("sector_heat", "sector_breadth") else np.nan
        feats.append({"Feature": _PRETTY.get(f, f), "Percentile": pct,
                      "Raw": r.get(f"raw_{f[2:]}", r.get(f))})
    fd = pd.DataFrame(feats).sort_values("Percentile", ascending=False, na_position="last")
    st.dataframe(
        fd.style.format({"Percentile": "{:.0%}", "Raw": "{:,.2f}"})
          .background_gradient(subset=["Percentile"], cmap="RdYlGn", vmin=0, vmax=1),
        use_container_width=True, hide_index=True, height=min(35 * (len(fd) + 1), 520))

    # ── Layer 3: evidence ─────────────────────────────────────────────────
    st.markdown("##### Trajectory")
    hist = scored[scored["ticker"] == ticker].sort_values("date")
    if len(hist) > 2:
        chart = hist.set_index("date")[["p_range_pos"]].rename(
            columns={"p_range_pos": "Position-in-range percentile"})
        st.line_chart(chart, height=220)
        st.caption(f"{len(hist)} weeks of history. This percentile — where the stock sits in "
                   "its own 52-week range, ranked against the universe — is the single factor "
                   "that survived the audit (IC ≈ 0.076 at 8 weeks).")
    else:
        st.caption("Not enough history to plot a trajectory yet.")
