"""
ui.ui_scanner — Tab 2. Deep Scanner: the funnel, with a memory.

This module is the deliberate STATEFUL counterpart to the stateless tear sheet
(PRISM convention). It OWNS the filter cascade and its `sc_*` session_state keys.
Do not harmonize the two files — the split is the point.

DESIGN: you screen on CHARACTERISTICS and read off PROBABILITIES.

That ordering is deliberate. Characteristics (sector, persistence, position in
range, sector heat) exist for every week in the archive, so the scanner can tell
you what a screen HISTORICALLY produced. Probabilities only exist for the newest
week, so filtering on them would leave nothing to check against.

That check is the thing a score-based scanner can never offer: a score has no
base rate, so "top 50 by score" is unfalsifiable. A screen on features can be
run over 45,000 labelled rows and graded.

And because a checkable screen is also a p-hacking machine, the honesty counter
comes with it — same as the Lab.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from core.config import WAVE_PCT, LABEL_HORIZON_WEEKS
from core.search import screen_hit_rate, search
from ui.ui_components import download, prob_table, stat_strip

# Presets are ANGLES on the same data, not tuned parameters — each states a
# thesis in plain language so it can be argued with.
QUICK_SCREENS = {
    "None": {},
    "🌊 Fresh waves": {"persist": (1, 4), "range_pos": 0.80,
                       "why": "just entered the top of their range — the move is young"},
    "🏔️ Persistent leaders": {"persist": (8, 99), "range_pos": 0.67,
                              "why": "held the top tercile 8+ weeks — proven, possibly extended"},
    "🔥 Hot sector": {"sector_heat": 0.60, "range_pos": 0.67,
                      "why": "strong stock inside a sector that is running"},
    "💎 Quiet strength": {"persist": (4, 99), "range_pos": 0.67, "max_heat": 0.50,
                          "why": "strong stock in a COLD sector — not a crowd trade"},
}


def _pct_slider(label, key, default=0.0, help=None):
    return st.slider(label, 0.0, 1.0, default, 0.05, key=key, help=help,
                     format="%.2f")


def render(ctx: dict) -> None:
    scored, meta = ctx["scored"], ctx["meta"]
    week = scored[scored["date"] == meta["latest"]].copy()

    st.subheader("Deep Scanner")
    st.caption(f"Every investable stock in the {meta['latest']:%d %b %Y} snapshot. "
               "Screen on characteristics · read off odds · **see what the screen "
               "historically produced.**")

    # ── search ────────────────────────────────────────────────────────────
    q = st.text_input("🔎 Find a stock", key="sc_q",
                      placeholder="ticker or company name — e.g. SWANDEF, or 'swan', or 'defence'")
    if q:
        hits = search(week, q)
        st.caption(f"{len(hits)} match{'es' if len(hits) != 1 else ''}")
        if len(hits):
            prob_table(hits.head(25))
        else:
            st.info("No match in this week's investable universe. It may have failed "
                    "the price / market-cap / turnover screen.")
        st.divider()

    # ── screen ────────────────────────────────────────────────────────────
    preset_name = st.radio("Quick screen", list(QUICK_SCREENS), horizontal=True, key="sc_preset")
    preset = QUICK_SCREENS[preset_name]
    if preset.get("why"):
        st.caption(f"*{preset['why']}*")

    c1, c2, c3 = st.columns(3)
    sectors = sorted(week["sector"].dropna().unique())
    pick = c1.multiselect("Sector", sectors, key="sc_sectors")
    cats = sorted(week["category"].dropna().unique())
    cat = c2.multiselect("Category", cats, key="sc_cats")
    persist_lo, persist_hi = c3.slider(
        "Persistence (weeks in top tercile)", 0, 52,
        preset.get("persist", (0, 52)), key="sc_persist")

    c4, c5 = st.columns(2)
    with c4:
        min_pos = _pct_slider("Min position in 52w range (percentile)", "sc_pos",
                              preset.get("range_pos", 0.0),
                              "The one factor that survived the audit.")
    with c5:
        min_heat = _pct_slider("Min sector heat", "sc_heat", preset.get("sector_heat", 0.0),
                               "Sector's average position-in-range percentile.")
    max_heat = preset.get("max_heat", 1.0)

    # The mask is built from FEATURES only, so the identical logic can be replayed
    # over the whole labelled archive below.
    def build_mask(frame: pd.DataFrame) -> pd.Series:
        m = pd.Series(True, index=frame.index)
        if pick:
            m &= frame["sector"].isin(pick)
        if cat:
            m &= frame["category"].isin(cat)
        m &= frame["persist"].between(persist_lo, persist_hi)
        m &= frame["p_range_pos"].fillna(-1) >= min_pos
        m &= frame["sector_heat"].fillna(-1) >= min_heat
        if max_heat < 1.0:
            m &= frame["sector_heat"].fillna(2) <= max_heat
        return m

    f = week[build_mask(week)].sort_values("net_edge", ascending=False)

    # ── the funnel ────────────────────────────────────────────────────────
    hist = screen_hit_rate(scored, build_mask(scored))
    if np.isfinite(hist["rate"]):
        lift = hist["lift"]
        tone = "good" if lift >= 1.3 else ("warn" if lift >= 1.0 else "bad")
        hist_card = (f"{hist['rate']:.1%}", f"base {hist['base']:.1%} · lift {lift:.2f}×", tone)
    else:
        hist_card = ("—", f"only {hist['n']} past matches — too few to grade", "warn")

    stat_strip([
        ("Investable this week", f"{len(week):,}", f"{meta['latest']:%d %b}", ""),
        ("Pass your screen", f"{len(f):,}",
         f"{len(f)/max(len(week),1)*100:.0f}% of the universe", ""),
        (f"Historical wave rate", hist_card[0], hist_card[1], hist_card[2]),
        ("Evidence behind it", f"{hist['n']:,}", f"rows over {hist['weeks']} weeks", ""),
    ])
    st.caption(
        f"**Historical wave rate** = of every past stock-week matching *these same "
        f"characteristics*, how many rose ≥{WAVE_PCT:.0f}% over the next "
        f"{LABEL_HORIZON_WEEKS} weeks. This is a screen you can check — a score-based "
        f"scanner cannot offer it. "
        f"⚠️ It is also measured on data the screen was built by looking at: slide the "
        f"filters until the number improves and you have discovered nothing. Treat it "
        f"as a sanity check, never as a finding — findings need a row in "
        f"`docs/TEST_LEDGER.md`.")

    st.divider()
    if not len(f):
        st.info("No stocks pass this screen.")
        return
    prob_table(f.head(200), height=560)
    if len(f) > 200:
        st.caption(f"Showing the top 200 of {len(f):,} by net edge. Download for the rest.")
    download(f, "⬇️ Download this screen",
             f"wave3_scan_{meta['latest']:%Y-%m-%d}.csv")
