"""
WAVE 3.0 — the app. Thin by design: this file owns navigation and selection
state, nothing else. Every number comes from core/; every pixel from ui/.

    streamlit run app.py                        (standalone repo)
    streamlit run alpha/app.py                  (inside the PRISM tree)

Six tabs, mirroring PRISM: Summary · Deep Scanner · The Tear Sheet · Pulse ·
Backtest · Reference. If you find yourself computing something here, it belongs
in core/ — that separation is why this app can be trusted and the last one
could not.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import streamlit as st

# Make `core` / `ui` importable whether this runs from the repo root (Streamlit
# Cloud) or as alpha/app.py inside the PRISM working tree.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from core.config import MAX_PER_SECTOR, MODEL_VERSION, TOP_N, UNIVERSE_CATEGORY  # noqa: E402
from core.decide import score_panel                                      # noqa: E402
from core.track_record import summary as track_summary                   # noqa: E402
from core.sources import (LOCAL_ARCHIVE, build_panel_from_files,      # noqa: E402
                          load_csvs_from_drive, local_archive_files)
from ui import (ui_backtest, ui_components, ui_pulse, ui_reference,      # noqa: E402
                ui_scanner, ui_summary, ui_tearsheet)

st.set_page_config(page_title=f"WAVE {MODEL_VERSION}", page_icon="🌊", layout="wide")


# ── Pipeline (cached; the only place stages are chained in the app) ───────────

@st.cache_data(show_spinner="Building the panel and scoring the newest week…",
               max_entries=2)
def _pipeline(files):
    """files (bytes -> hashable) in, everything out.

    ONE cached entry keyed on the raw file bytes. Handing a DataFrame to
    @st.cache_data means it must hash one, and a panel carrying non-picklable
    content raises UnhashableParamError at runtime. Bytes always hash.

    Selection routes through core.decide.score_panel — the SAME function the CLI
    and CI use — so the app can never rank differently from the frozen log."""
    panel = build_panel_from_files(files)
    table, meta, scored = score_panel(panel)
    # The live track record: frozen forecasts vs what actually happened.
    history = track_summary(panel)
    return table, meta, scored, history


# ── Sidebar: data source ─────────────────────────────────────────────────────

def _sidebar():
    with st.sidebar:
        st.title("🌊 WAVE")
        st.caption(f"v{MODEL_VERSION} · probability engine")
        st.divider()
        opts = ["Google Drive folder", "Upload CSVs"]
        if os.path.isdir(LOCAL_ARCHIVE):
            opts.insert(0, "Local archive")
        src = st.radio("Weekly snapshots", opts, key="src")
        files = None
        if src == "Local archive":
            if st.button("Load archive", type="primary", use_container_width=True):
                files = local_archive_files()
        elif src == "Google Drive folder":
            key = st.text_input("Public folder link or key", key="drive_key")
            if st.button("Load from Drive", type="primary", use_container_width=True) and key:
                with st.spinner("Downloading…"):
                    files, err = load_csvs_from_drive(key)
                if err:
                    st.error(err)
        else:
            up = st.file_uploader("Stocks_Weekly_*.csv", type="csv",
                                  accept_multiple_files=True)
            if up and st.button("Load uploads", type="primary", use_container_width=True):
                files = [(f.name, f.getvalue()) for f in up]
        if files:
            st.session_state["files"] = files
            st.cache_data.clear()
        st.divider()
        st.caption(f"{UNIVERSE_CATEGORY} · top {TOP_N} · max {MAX_PER_SECTOR}/sector · "
                   "laws in **Reference**")
    return st.session_state.get("files")


def main() -> None:
    ui_components.inject_css()
    files = _sidebar()
    if not files:
        st.title("🌊 WAVE 3.0")
        st.info("Load the weekly snapshots from the sidebar to begin.", icon="👈")
        st.caption("A probability engine: for every stock, the modelled odds of a wave "
                   "(+15% in 4 weeks) and of a crash — judged by whether those odds come true.")
        return

    table, meta, scored, history = _pipeline(files)
    ctx = {"table": table, "meta": meta, "scored": scored, "history": history}

    tabs = st.tabs(["📊 Summary", "🔍 Deep Scanner", "🔬 The Tear Sheet",
                    "🌊 Pulse", "🧪 Backtest", "📖 Reference"])
    with tabs[0]:
        ui_summary.render(ctx)
    with tabs[1]:
        ui_scanner.render(ctx)
    with tabs[2]:
        # app.py owns selection state; ui_tearsheet stays stateless by contract.
        week = scored[scored["date"] == meta["latest"]]
        choices = week.sort_values("net_edge", ascending=False)["ticker"].dropna().tolist()
        pick = st.selectbox("Stock", choices, key="ts_ticker",
                            help="Ordered by net edge. Type to search.")
        ui_tearsheet.render(ctx, pick)
    with tabs[3]:
        ui_pulse.render(ctx)
    with tabs[4]:
        ui_backtest.render(ctx)
    with tabs[5]:
        ui_reference.render(ctx)


if __name__ == "__main__" or st.runtime.exists():
    main()
