"""
ui.ui_summary — Tab 1. The landing page.

Design law: NEVER SHOW A PREDICTION WITHOUT ITS TRACK RECORD. The experiment's own
record sits above the picks, permanently coupling the claim to its history. That
coupling is the one surface neither legacy app had — and its absence is where nine
months of unchecked confidence lived.

Reading order is deliberate, top to bottom:

  1. WHAT THIS WEEK SAYS   one sentence, plain English, no jargon
  2. THE EXPERIMENT        weeks frozen / 26, what has been graded, what has not
  3. THE EVIDENCE          the counted decile curve — the whole engine in one image
  4. THIS WEEK             snapshot facts
  5. THE PICKS             top 10, full 30 downloadable
  6. WHAT TO DO            the rules, including "not yet"

Nothing here computes. Every number arrives via ctx from core/.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.config import (COST_BPS, HOLD_WEEKS, LABEL_HORIZON_WEEKS, MAX_PER_SECTOR,
                         TOP_N, TRAIL_STOP_PCT, UNIVERSE_CATEGORIES, WAVE_PCT)
from ui.ui_components import (decile_bars, download, experimental_banner,
                              prob_table, stat_strip)


def _hero(meta: dict, table: pd.DataFrame) -> None:
    """The one-sentence answer, before any table or chart."""
    shape = meta.get("shape")
    if not shape or table.empty:
        return
    rate, base, lift = shape["top_rate"], shape["base"], shape["top_lift"]
    n = shape["top_n"]
    st.markdown(
        f'<div class="wv-hero"><b>{len(table)} stocks, all sitting in the top decile '
        f'of their 52-week range.</b>'
        f'<p>Of <b>{n:,}</b> past stock-weeks in that same position, '
        f'<b>{rate:.1%}</b> rose {WAVE_PCT:.0f}% or more within '
        f'{LABEL_HORIZON_WEEKS} weeks — against <b>{base:.1%}</b> for the universe '
        f'as a whole. That is a <b>{lift:.2f}×</b> edge.<br>'
        f'It is a count of what already happened, not a forecast about these '
        f'companies. Roughly <b>{1 - rate:.0%}</b> of them will not wave.</p></div>',
        unsafe_allow_html=True)


def _experiment(prog: dict, hist: dict | None) -> None:
    """Weeks banked against the 26 the pre-registration demands."""
    st.subheader("The experiment")
    st.caption("Forecasts are frozen to `logs/waves_log.csv` before their outcomes "
               "exist, and never edited. This counter — not the picks — is what the "
               "system is actually building.")

    weeks, target = prog["weeks"], prog["target"]
    pct = min(100.0, weeks / target * 100.0) if target else 0.0
    st.markdown(f'<div class="wv-prog"><i style="width:{pct:.1f}%"></i></div>'
                f'<div class="wv-dfoot">{weeks} of {target} weeks frozen '
                f'&nbsp;·&nbsp; first verdict 21 Feb 2027</div>',
                unsafe_allow_html=True)

    cards = [("Weeks frozen", f"{weeks} / {target}",
              f"{prog['rows']:,} forecasts logged", "good" if weeks else "warn"),
             ("Graded so far", f"{prog['graded']}",
              "outcome fully elapsed", "" if prog["graded"] else "warn"),
             ("Still in flight", f"{prog['pending']}",
              "neither hit nor miss yet", "")]
    if prog.get("next_grade") is not None:
        cards.append(("Next gradeable", f"{prog['next_grade']:%d %b %Y}",
                      "newest forecast resolves", ""))
    stat_strip(cards)

    if hist:
        gap = hist["gap_pp"]
        tone = "good" if abs(gap) <= 5 else ("warn" if abs(gap) <= 10 else "bad")
        stat_strip([
            ("Model said", f"{hist['stated']:.1%}",
             f"{hist['n']:,} forecasts over {hist['weeks']} weeks", ""),
            ("Reality delivered", f"{hist['actual']:.1%}", "same forecasts", ""),
            ("Gap", f"{gap:+.1f}pp", "honest bar: ±5pp", tone),
            ("Lift vs base", f"{hist['lift']:.2f}×", f"base {hist['base']:.1%}", ""),
        ])
        # WHICH evidence this is must never be ambiguous. Substituting a backtest
        # for a live record is precisely the move this project exists to prevent.
        if hist["source"] == "live log":
            st.success(f"**Live record** — {hist['n']:,} forecasts frozen *before* "
                       "their outcomes existed. This is evidence.", icon="🔒")
        else:
            st.warning("**Backtest, not a live record.** Computed with today's code "
                       "over past data, so it is weaker evidence than a frozen "
                       "forecast.", icon="⚠️")
    elif prog["weeks"]:
        st.info(f"**No verdict yet, and that is correct.** {prog['weeks']} week(s) "
                f"frozen, none aged past {LABEL_HORIZON_WEEKS} weeks. The first "
                "grades arrive "
                + (f"**{prog['next_grade']:%d %b %Y}**." if prog.get("next_grade")
                   else "once a forecast resolves.")
                + " Until then the honest answer to *does this work* is **unknown**.",
                icon="⏳")
    else:
        st.info("Nothing frozen yet. `python -m core.decide` writes the first row.",
                icon="👋")


def _evidence(meta: dict) -> None:
    """The counted curve. The whole engine, in one picture."""
    shape = meta.get("shape")
    deciles = meta.get("deciles")
    if deciles is None or deciles.empty or not shape:
        return
    st.subheader("Why the top decile")
    st.caption(f"Every past stock-week in {meta.get('odds_basis', 'the universe')}, "
               f"sorted by position in its 52-week range and split into ten groups. "
               f"Bars are counted outcomes — no model, nothing fitted.")
    decile_bars(deciles, highlight=int(deciles["decile"].max()))

    trough, u = shape["trough_decile"], shape["u_shape"]
    d1, base = float(deciles["rate"].iloc[0]), shape["base"]
    # Say exactly what the numbers show. "The middle is worst" is only true when
    # the trough IS in the middle, and the bottom decile beating the trough is not
    # the same as it beating the base — it usually does not.
    where = "the middle" if 4 <= trough <= 7 else f"decile {trough}"
    if d1 > base * 0.9:
        left = (f"the bottom decile ({d1:.1%}) does beat it — though it still "
                f"trails the {base:.1%} base")
    else:
        left = "the bottom decile is no refuge either"
    st.markdown(
        f"**The curve bends — it is not a ramp.** The weakest place to sit is "
        f"{where} at {deciles['rate'].min():.1%}, and {left}. "
        + ("Both ends beat the trough, which is the U holding. " if u else
           "**Both ends no longer beat the trough — the U has flattened. Watch it.** ")
        + "That bend is also why a fitted model lost to plain counting: a "
          "regression draws a straight line, and the truth here curves.")


def render(ctx: dict) -> None:
    table, meta, scored = ctx["table"], ctx["meta"], ctx["scored"]
    report, prog = ctx.get("report"), ctx.get("progress") or {}
    prog = {**{"weeks": 0, "rows": 0, "graded": 0, "pending": 0, "target": 26,
               "next_grade": None}, **prog}

    _hero(meta, table)
    _experiment(prog, ctx.get("history"))
    experimental_banner()
    st.divider()

    _evidence(meta)
    st.divider()

    st.subheader("This week")
    inuni = meta.get("universe_traded", meta.get("universe", 0))
    strip = [
        ("Snapshot", f"{meta['latest']:%d %b %Y}", "newest weekly file", ""),
        ("Trained through", f"{meta['trained_through']:%d %b}",
         f"{meta['weeks']} weeks of resolved outcomes", ""),
        (f"Base rate (≥{WAVE_PCT:.0f}% / {LABEL_HORIZON_WEEKS}w)",
         f"{meta['base_up']:.1%}", "the universe's own hit rate", ""),
        ("Buyable this week", f"{inuni:,}",
         f"{meta.get('odds_basis', '')}, past the screen", ""),
    ]
    if report is not None:
        strip.append(("Data health", f"{report.delistings} delisted",
                      f"{report.corporate_actions} corp-actions quarantined", ""))
    stat_strip(strip)

    st.subheader(f"Top 10 of {len(table)}")
    st.caption("Ranked on the one factor that survived measurement. Every row shows "
               "the same historical rate because they all sit in the same decile — "
               "that is what a counted rate means. The full filterable list is in "
               "**Deep Scanner**; one stock in depth is in **The Tear Sheet**.")
    prob_table(table.head(10))
    download(table, f"⬇️ Download the full top-{len(table)}",
             f"wave3_forecast_{meta['latest']:%Y-%m-%d}.csv")

    with st.expander("What to actually do with this list"):
        st.markdown(f"""
**Right now: nothing. Collect weeks.** The system has {prog['weeks']} of
{prog['target']}. Trading an unproven edge is how the last system lost money while
reporting gains.

When it *is* traded, the rules are fixed in `config.py` and are not suggestions:

| Rule | Value | Why |
|---|---|---|
| Hold | **{HOLD_WEEKS} weeks** | ~75% of this list changes weekly. Chasing it costs ~22%/yr in friction against a ~2%/yr edge. |
| Stop | **−{TRAIL_STOP_PCT:.0f}% trailing**, daily closes | Weekly closes overstate stop performance by up to 22pp/yr — they cannot see a mid-week collapse. |
| Position cap | **{MAX_PER_SECTOR} per sector** | The seatbelt. Not tunable, whatever sector heat says. |
| Size | **{TOP_N} names** | Breadth is where a small edge becomes a real one. |
| Costs assumed | **{COST_BPS:.1f} bps** round trip | Realistic Indian STT + brokerage + impact. |

The holding period is the **least** proven number here: {HOLD_WEEKS} weeks won a
four-horizon test at t=1.45, which does not clear the multiple-testing bar
(ledger #59–63). One year of data gives six independent {HOLD_WEEKS}-week windows —
too few to separate it from 12. It stays until February gives out-of-sample
evidence.
""")
