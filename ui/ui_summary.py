"""
ui.ui_summary — Tab 1. The landing page.

Design law: NEVER SHOW A PREDICTION WITHOUT ITS TRACK RECORD. The calibration
strip sits at the very top, above the picks, permanently coupling the claim to
its history. That coupling is the one surface neither legacy app had — and its
absence is where nine months of unchecked confidence lived.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.config import LABEL_HORIZON_WEEKS, UNIVERSE_CATEGORY, WAVE_PCT
from ui.ui_components import download, experimental_banner, prob_table, stat_strip


def render(ctx: dict) -> None:
    table, meta, scored = ctx["table"], ctx["meta"], ctx["scored"]
    report = ctx.get("report")

    st.subheader("Track record")
    st.caption("Every forecast this model has made against outcomes that have since "
               "resolved. This is the only number that decides whether the odds below "
               "are worth reading.")
    hist = ctx.get("history")
    if hist is None or hist.empty:
        stat_strip([("Graded forecasts", "—", "needs 26+ training weeks", "warn")])
        st.info("No graded history yet. The Backtest tab's **Calibration audit** runs "
                "the full walk-forward on demand.")
    else:
        stated, actual = hist["stated"], hist["actual"]
        gap = (actual - stated) * 100
        tone = "good" if abs(gap) <= 5 else ("warn" if abs(gap) <= 10 else "bad")
        stat_strip([
            ("Model said", f"{stated:.1%}", f"avg over {hist['weeks']} weeks", ""),
            ("Reality delivered", f"{actual:.1%}", "same weeks", ""),
            ("Calibration gap", f"{gap:+.1f}pp", "honest bar: ±5pp", tone),
            ("Top-decile lift", f"{hist['lift']:.2f}×", "vs base rate", ""),
        ])

    experimental_banner()
    st.divider()

    st.subheader("This week")
    base = meta["base_up"]
    inuni = int(scored[scored["date"] == meta["latest"]].shape[0])
    strip = [
        ("Snapshot", f"{meta['latest']:%d %b %Y}", "newest weekly file", ""),
        ("Trained through", f"{meta['trained_through']:%d %b}", f"{meta['weeks']} weeks", ""),
        (f"Base P(wave ≥{WAVE_PCT:.0f}%/{LABEL_HORIZON_WEEKS}w)", f"{base:.1%}",
         "the universe's own hit rate", ""),
        ("Investable universe", f"{inuni:,}", f"{UNIVERSE_CATEGORY} + screen", ""),
    ]
    if report is not None:
        strip.append(("Data health", f"{report.delistings} delisted",
                      f"{report.corporate_actions} corp-actions quarantined", ""))
    stat_strip(strip)

    st.subheader("Top 10 by net edge")
    st.caption("Net edge = P(wave) − P(crash). The full, filterable list lives in "
               "**Deep Scanner**; one stock in depth lives in **The Tear Sheet**.")
    prob_table(table.head(10))
    download(table, "⬇️ Download the full top-30",
             f"wave3_forecast_{meta['latest']:%Y-%m-%d}.csv")
