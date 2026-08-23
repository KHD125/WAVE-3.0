"""
ui.ui_components — shared render primitives. Compact inline HTML/CSS instead of
st.columns/st.metric everywhere (PRISM convention: Streamlit's own layout
primitives bloat vertical padding badly on dense tables).

Nothing here computes. If a function in this file starts deciding something,
it belongs in core/.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

# The banner that cannot be removed until calibration passes (docs/PLAN.md §9).
EXPERIMENTAL_NOTE = (
    "**EXPERIMENTAL** — this model failed its first calibration audit by up to "
    "+16pp (regime shift; ledger #53). The probabilities are its honest best "
    "estimate, not settled truth. The frozen forecast log is the only judge."
)


def inject_css() -> None:
    st.markdown("""
    <style>
      .wv-strip{display:flex;gap:10px;flex-wrap:wrap;margin:2px 0 10px 0}
      .wv-card{flex:1 1 150px;background:rgba(255,255,255,.04);
               border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:9px 12px}
      .wv-lab{font-size:.68rem;letter-spacing:.5px;text-transform:uppercase;
              opacity:.62;margin-bottom:3px}
      .wv-val{font-size:1.35rem;font-weight:650;line-height:1.15}
      .wv-sub{font-size:.72rem;opacity:.58;margin-top:2px}
      .wv-good{color:#4ade80} .wv-bad{color:#f87171} .wv-warn{color:#fbbf24}
      div[data-testid="stDataFrame"]{font-variant-numeric:tabular-nums}
    </style>""", unsafe_allow_html=True)


def stat_strip(cards) -> None:
    """cards: iterable of (label, value, subtext, tone) — tone in '', 'good', 'bad', 'warn'."""
    html = ['<div class="wv-strip">']
    for label, value, sub, tone in cards:
        cls = f" wv-{tone}" if tone else ""
        html.append(
            f'<div class="wv-card"><div class="wv-lab">{label}</div>'
            f'<div class="wv-val{cls}">{value}</div>'
            f'<div class="wv-sub">{sub}</div></div>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def experimental_banner() -> None:
    st.warning(EXPERIMENTAL_NOTE, icon="⚠️")


def prob_table(df: pd.DataFrame, height: int | None = None) -> None:
    """The canonical forecast table rendering — one definition, used by every tab."""
    # v3.1: every column is a FACT. `hist_rate` is a counted frequency over the
    # archive, not a fitted probability — see core/counted.py.
    cols = {"ticker": "Ticker", "company_name": "Company", "sector": "Sector",
            "price": "Price ₹", "p_range_pos": "Range pos", "decile": "Decile",
            "hist_rate": "Hist wave rate", "persist": "Persist w",
            "sector_heat": "Sector heat", "from_high": "From high %"}
    view = df[[c for c in cols if c in df.columns]].rename(columns=cols)
    if "Range pos" in view:
        view["Range pos"] = view["Range pos"] * 100.0
    st.dataframe(
        view, use_container_width=True, hide_index=True,
        height=height or min(38 * (len(view) + 1) + 3, 720),
        column_config={
            "Price ₹": st.column_config.NumberColumn(format="%.0f"),
            "Range pos": st.column_config.ProgressColumn(
                "Range pos", help="Percentile position within its own 52-week range",
                format="%.0f", min_value=0, max_value=100),
            "Decile": st.column_config.NumberColumn(format="%.0f"),
            "Hist wave rate": st.column_config.NumberColumn(
                "Hist wave rate",
                help="Of all past stock-weeks in this decile, how many rose >=15% "
                     "in 4 weeks. A COUNT of your data, not a forecast.",
                format="%.1f%%"),
            "Sector heat": st.column_config.NumberColumn(format="%.2f"),
            "From high %": st.column_config.NumberColumn(format="%.1f"),
        })


def download(df: pd.DataFrame, label: str, filename: str) -> None:
    st.download_button(label, df.to_csv(index=False).encode("utf-8"),
                       file_name=filename, mime="text/csv")
