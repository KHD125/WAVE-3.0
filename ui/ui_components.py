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
# The old text cited a +16pp calibration miss — that was v3.0's FITTED logistic,
# retired in v3.1. Nothing is fitted now, so nothing can be miscalibrated; the open
# question moved from "are the odds honest?" to "do they PERSIST?". Leaving the
# retired model's failure on screen would be its own small dishonesty.
EXPERIMENTAL_NOTE = (
    "**EXPERIMENTAL — nothing here is proven.** The rates are COUNTED from past "
    "data, not predicted, so they cannot be miscalibrated. Whether they PERSIST is "
    "exactly what the frozen log is testing. Expect **~2%/yr** excess, not 15%. "
    "First verdict **21 Feb 2027** — until then this is evidence being collected, "
    "not advice."
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
      .wv-dwrap{position:relative;display:flex;align-items:flex-end;gap:6px;
                height:190px;padding:16px 6px 0 6px;margin:4px 0 2px 0;
                background:rgba(255,255,255,.02);border-radius:9px}
      .wv-dcol{flex:1;display:flex;flex-direction:column;justify-content:flex-end;
               align-items:center;height:100%}
      .wv-dbar{width:100%;border-radius:4px 4px 0 0;transition:height .2s}
      .wv-dval{font-size:.66rem;opacity:.66;margin-bottom:3px;font-variant-numeric:tabular-nums}
      .wv-dlab{font-size:.68rem;opacity:.5;margin-top:4px}
      .wv-dbase{position:absolute;left:6px;right:6px;border-top:1px dashed rgba(251,191,36,.75);
                pointer-events:none}
      .wv-dbase span{position:absolute;right:0;top:-15px;font-size:.63rem;color:#fbbf24;opacity:.9}
      .wv-dfoot{font-size:.7rem;opacity:.55;margin:0 0 10px 2px}
      .wv-prog{height:9px;border-radius:5px;background:rgba(255,255,255,.08);
               overflow:hidden;margin:6px 0 4px 0}
      .wv-prog i{display:block;height:100%;background:linear-gradient(90deg,#38bdf8,#4ade80)}
      .wv-hero{background:linear-gradient(135deg,rgba(56,189,248,.10),rgba(74,222,128,.07));
               border:1px solid rgba(255,255,255,.10);border-radius:11px;
               padding:14px 17px;margin:2px 0 12px 0}
      .wv-hero b{font-size:1.06rem}
      .wv-hero p{margin:6px 0 0 0;font-size:.83rem;opacity:.78;line-height:1.5}
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


def decile_bars(table: pd.DataFrame, highlight: int | None = None) -> None:
    """The counted curve: historical wave rate per decile, with the base rate line.

    THE most informative object in the system and no surface showed it. The shape
    is a U, not a ramp (ledger #58) — extremes carry the signal, the middle is
    dead — which is also why fitting a monotone model to it underperformed simply
    counting. A reader who sees this understands the whole engine in one glance.
    """
    if table is None or table.empty:
        return
    base = float(table["base"].iloc[0])
    top = float(table["rate"].max())
    span = max(top, base) * 1.15 or 1.0
    bars = []
    for _, r in table.iterrows():
        dec, rate, n = int(r["decile"]), float(r["rate"]), int(r["n"])
        h = max(2.0, rate / span * 100.0)
        on = (highlight is not None and dec == highlight)
        colour = "#4ade80" if on else "rgba(255,255,255,.22)"
        edge = "border:1px solid #4ade80;" if on else "border:1px solid transparent;"
        bars.append(
            f'<div class="wv-dcol" title="Decile {dec}: {rate:.2%} of {n:,} past '
            f'stock-weeks waved">'
            f'<div class="wv-dval">{rate*100:.1f}</div>'
            f'<div class="wv-dbar" style="height:{h:.1f}%;background:{colour};{edge}"></div>'
            f'<div class="wv-dlab">{dec}</div></div>')
    baseline = base / span * 100.0
    st.markdown(
        f'<div class="wv-dwrap"><div class="wv-dbase" style="bottom:{baseline:.1f}%">'
        f'<span>base {base:.1%}</span></div>{"".join(bars)}</div>'
        f'<div class="wv-dfoot">Position in 52-week range, decile 1 (lowest) to 10 '
        f'(highest) &nbsp;·&nbsp; bar = % of past stock-weeks that rose '
        f'&ge;15% within 4 weeks</div>', unsafe_allow_html=True)


def download(df: pd.DataFrame, label: str, filename: str) -> None:
    st.download_button(label, df.to_csv(index=False).encode("utf-8"),
                       file_name=filename, mime="text/csv")
