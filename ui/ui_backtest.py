"""
ui.ui_backtest — Tab 5. The Lab.

This is Alpha Trajectory's Pattern Analyser + Strategy Backtest + DNA Backtest,
fused into one honest engine. The machinery in those tabs was RIGHT — take weekly
CSVs, compute forward returns by group, report. It was aimed at 42 invented
patterns instead of measurable features, and it reported cost-free arithmetic
means with no t-stats. Same engine, true content, and one addition:

    THE TEST COUNTER.

Explore as much as you like. The Lab simply refuses to let you forget how much
you have explored — because at N tests, noise alone produces max|t| ≈ sqrt(2·ln N),
and a finding that doesn't clear its own bar isn't a finding.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
import streamlit as st

from core.config import COST_BPS, LABEL_HORIZON_WEEKS, WAVE_PCT
from core.odds import brier_score, calibration_table, walk_forward
from ui.ui_components import download, stat_strip

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(_ROOT, "docs", "TEST_LEDGER.md")
PRIOR_TESTS = 54          # the audit burn + T1/T2 + the streak re-run (ledger #1-54)

_PROFILE_FEATURES = [
    ("p_range_pos", "Position in 52w range"), ("p_from_high", "Nearness to 52w high"),
    ("p_ret_7d", "1-week return"), ("p_ret_30d", "1-month return"),
    ("p_ret_6m", "6-month return"), ("p_rvol", "Relative volume"),
    ("p_vol_trend", "Volume trend"), ("p_px_sma50", "Price vs 50d avg"),
    ("p_px_sma200", "Price vs 200d avg"), ("p_log_mcap", "Size"),
    ("persist", "Persistence (wk)"), ("sector_heat", "Sector heat"),
]


def _noise_bar(n_tests: int) -> float:
    """E[max |t|] over n independent draws from N(0,1) — the bar a finding must clear."""
    return float(np.sqrt(2.0 * np.log(max(n_tests, 2))))


def _counter(extra: int = 0) -> None:
    n = PRIOR_TESTS + st.session_state.get("lab_runs", 0) + extra
    bar = _noise_bar(n)
    st.caption(f"🧪 **Test #{n}** on this dataset · at {n} tests, pure noise produces "
               f"|t| ≈ **{bar:.1f}** · a result below that is not a finding. "
               f"Every run belongs in `docs/TEST_LEDGER.md`.")


def _bump() -> None:
    st.session_state["lab_runs"] = st.session_state.get("lab_runs", 0) + 1


def render(ctx: dict) -> None:
    scored = ctx["scored"]
    st.subheader("The Lab")
    st.caption("Alpha Trajectory's Pattern Analyser engine, pointed at measurable features "
               "and wired to an honesty meter.")
    _counter()

    t1, t2, t3, t4 = st.tabs(["🔥 Gainers vs Losers", "📉 IC by horizon",
                              "⚖️ Calibration audit", "📒 Test ledger"])

    # ── 1. what did the winners look like BEFORE they won ──────────────────
    with t1:
        st.caption(f"Split each week's universe by what it did over the next "
                   f"{LABEL_HORIZON_WEEKS} weeks, then look at what those groups looked like "
                   "**beforehand**. The audit's headline warning lives here: on raw momentum "
                   "features, future losers scored *higher* than future gainers — these "
                   "signals detect movement, not direction.")
        col = f"fwd_ret_{LABEL_HORIZON_WEEKS}w"
        d = scored[scored[col].notna()].copy()
        if d.empty:
            st.info("No resolved outcomes in this panel yet.")
        else:
            q = st.select_slider("Group size", options=[5, 10, 20], value=5,
                                 format_func=lambda v: f"top/bottom {v}%", key="lab_q")
            d["grp"] = "middle"
            for _, g in d.groupby("date"):
                hi, lo = g[col].quantile(1 - q / 100), g[col].quantile(q / 100)
                d.loc[g.index[g[col] >= hi], "grp"] = "GAINER"
                d.loc[g.index[g[col] <= lo], "grp"] = "loser"
            rows = []
            for f, label in _PROFILE_FEATURES:
                if f not in d.columns:
                    continue
                a = d[d.grp == "GAINER"][f].median()
                b = d[d.grp == "middle"][f].median()
                c = d[d.grp == "loser"][f].median()
                rows.append({"Feature": label, "GAINER": a, "middle": b, "loser": c,
                             "G − mid": a - b, "G − loser": a - c})
            prof = pd.DataFrame(rows).sort_values("G − mid", ascending=False)
            st.dataframe(
                prof, use_container_width=True, hide_index=True,
                height=min(35 * (len(prof) + 1), 520),
                column_config={c: st.column_config.NumberColumn(format="%.3f")
                               for c in ("GAINER", "middle", "loser",
                                         "G − mid", "G − loser")})
            st.caption("**Read the `G − loser` column, not `G − mid`.** A feature that "
                       "separates gainers from the *middle* but not from *losers* is a "
                       "volatility detector wearing a direction costume.")

    # ── 2. horizon decay — the tool that would have caught it ──────────────
    with t2:
        st.caption("Rank correlation (Spearman IC) of each feature against forward returns, "
                   "one column per horizon. **This is the tool that was in the old app all "
                   "along** — its Strategy Backtest tab had 1w/4w/8w/13w sub-tabs. Read as "
                   "mean spreads with no t-stats, it hid the fact that these factors are "
                   "dead at 1 week and alive at 8.")
        horizons = [int(c.split("_")[2][:-1]) for c in scored.columns
                    if c.startswith("fwd_ret_")]
        if not horizons:
            st.info("This panel was built with a single horizon. Rebuild with more to compare.")
        elif st.button("Run IC by horizon", key="lab_ic"):
            _bump()
            from scipy.stats import spearmanr
            out = []
            for f, label in _PROFILE_FEATURES:
                if f not in scored.columns:
                    continue
                rec = {"Feature": label}
                for k in sorted(horizons):
                    ics = []
                    for _, g in scored.groupby("date"):
                        m = g[f].notna() & g[f"fwd_ret_{k}w"].notna()
                        if m.sum() > 150 and g.loc[m, f].nunique() > 5:
                            r = spearmanr(g.loc[m, f], g.loc[m, f"fwd_ret_{k}w"]).correlation
                            if np.isfinite(r):
                                ics.append(r)
                    a = np.asarray(ics)
                    rec[f"IC {k}w"] = a.mean() if len(a) else np.nan
                    # overlap haircut: k-week labels from weekly data are not independent
                    rec[f"t {k}w"] = ((a.mean() / (a.std(ddof=1) / np.sqrt(len(a))))
                                      / np.sqrt(k) if len(a) > 2 else np.nan)
                out.append(rec)
            res = pd.DataFrame(out)
            st.dataframe(res.style.format("{:+.4f}", subset=[c for c in res.columns
                                                             if c != "Feature"]),
                         use_container_width=True, hide_index=True)
            st.caption("t-stats are **overlap-adjusted** (÷√horizon): k-week forward returns "
                       "from weekly snapshots overlap, and the raw t-stat is inflated by "
                       "roughly that factor.")
            _counter(extra=0)

    # ── 3. does the model keep its promises ───────────────────────────────
    with t3:
        st.caption("The judge. Refits the model once per historical week, forecasting only "
                   "from weeks it has never seen, then asks: when it said X%, did X% happen?")
        if st.button("Run walk-forward calibration (slow)", key="lab_cal"):
            _bump()
            with st.spinner("Refitting once per week…"):
                oos = walk_forward(scored)
            if oos.empty:
                st.info("Not enough history yet — needs 26+ training weeks.")
            else:
                base = oos["y_up"].mean()
                top = oos[oos["p_up"] >= oos.groupby("date")["p_up"]
                          .transform(lambda s: s.quantile(0.9))]
                stat_strip([
                    ("OOS weeks", f"{oos['date'].nunique()}", f"{len(oos):,} rows", ""),
                    ("Brier P(wave)", f"{brier_score(oos):.4f}",
                     f"base-rate-only ≈ {base*(1-base):.4f}", ""),
                    ("Top-decile lift", f"{top['y_up'].mean()/base:.2f}×",
                     f"stated {top['p_up'].mean():.1%} · actual {top['y_up'].mean():.1%}", ""),
                    ("Crash in same names", f"{top['y_dn'].mean():.1%}",
                     f"base {oos['y_dn'].mean():.1%} — waves break both ways", "warn"),
                ])
                a, b = st.columns(2)
                a.markdown("**P(wave): stated vs actual**")
                a.dataframe(calibration_table(oos).style.format("{:.3f}"),
                            use_container_width=True, hide_index=True)
                b.markdown("**P(crash): stated vs actual**")
                b.dataframe(calibration_table(oos, "p_dn", "y_dn").style.format("{:.3f}"),
                            use_container_width=True, hide_index=True)
                st.caption("Honesty bar: |gap_pp| ≤ ~5 per decile. Failing keeps the model "
                           "**EXPERIMENTAL** — that is the pre-registered consequence, not "
                           "a reason to retune.")
                download(oos[["date", "ticker", "p_up", "p_dn", "y_up", "y_dn"]],
                         "⬇️ Download OOS forecasts", "wave3_oos.csv")

    # ── 4. the ledger ─────────────────────────────────────────────────────
    with t4:
        st.caption("Every hypothesis ever run against this dataset. The bar rises with the "
                   "length of this file — that is the point of keeping it.")
        if os.path.exists(LEDGER):
            st.markdown(open(LEDGER, encoding="utf-8").read())
        else:
            st.info("docs/TEST_LEDGER.md not found.")
