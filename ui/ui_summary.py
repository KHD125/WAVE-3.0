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

from core.config import LABEL_HORIZON_WEEKS, UNIVERSE_CATEGORIES, WAVE_PCT
from ui.ui_components import download, experimental_banner, prob_table, stat_strip


def render(ctx: dict) -> None:
    table, meta, scored = ctx["table"], ctx["meta"], ctx["scored"]
    report = ctx.get("report")

    st.subheader("Track record")
    st.caption("Every forecast this model has made against outcomes that have since "
               "resolved. This is the only number that decides whether the odds below "
               "are worth reading.")
    hist = ctx.get("history")
    if not hist:
        stat_strip([("Graded forecasts", "—", "none have aged past 4 weeks yet", "warn")])
        st.info("No graded forecasts yet. Every Sunday run freezes one to "
                "`logs/waves_log.csv`; four weeks later it can be marked hit or miss. "
                "Until then the **Backtest → Calibration audit** tab runs the "
                "walk-forward on demand.")
    else:
        gap = hist["gap_pp"]
        tone = "good" if abs(gap) <= 5 else ("warn" if abs(gap) <= 10 else "bad")
        live = hist["source"] == "live log"
        stat_strip([
            ("Model said", f"{hist['stated']:.1%}",
             f"{hist['n']:,} forecasts over {hist['weeks']} weeks", ""),
            ("Reality delivered", f"{hist['actual']:.1%}", "same forecasts", ""),
            ("Calibration gap", f"{gap:+.1f}pp", "honest bar: ±5pp", tone),
            ("Lift vs base", f"{hist['lift']:.2f}×", f"base {hist['base']:.1%}", ""),
        ])
        # WHICH evidence this is must never be ambiguous. Substituting a backtest
        # for a live record is precisely the move this project exists to prevent.
        if live:
            st.success(f"**Live record** — {hist['n']:,} forecasts frozen to the log "
                       "*before* their outcomes existed. This is evidence.", icon="🔒")
        else:
            pending = hist.get("pending", 0)
            st.warning(f"**Backtest, not a live record.** Computed with today's code over "
                       f"past data, so it is weaker evidence than a frozen forecast. "
                       f"{pending} logged forecast(s) still in flight — the live record "
                       "starts once they age past 4 weeks.", icon="⚠️")

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
        ("Investable universe", f"{inuni:,}", "Mid + Small + screen", ""),
    ]
    if report is not None:
        strip.append(("Data health", f"{report.delistings} delisted",
                      f"{report.corporate_actions} corp-actions quarantined", ""))
    stat_strip(strip)

    st.subheader("Top 10 by position in 52-week range")
    st.caption("Ranked on the one factor that survived measurement. The full, filterable list lives in "
               "**Deep Scanner**; one stock in depth lives in **The Tear Sheet**.")
    prob_table(table.head(10))
    download(table, "⬇️ Download the full top-30",
             f"wave3_forecast_{meta['latest']:%Y-%m-%d}.csv")
