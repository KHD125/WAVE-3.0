"""
WAVE 3.0 — Streamlit front end (the Sunday table, on a page).

Deliberately ONE page. The engine's honesty lives in alpha/PLAN.md's laws;
this file only displays what the pipeline computes — it adds no opinions,
no extra scores, no knobs that could quietly become parameters.

Data sources (sidebar):
  * Google Drive folder — your existing public backup folder of weekly CSVs
    (loader ported from Alpha Trajectory's proven implementation)
  * Upload CSVs        — drag the Stocks_Weekly_*.csv files in
  * Local archive      — auto-detected when running on the home machine

Runs locally (`streamlit run alpha/wave_app.py`) and on Streamlit Community
Cloud (repo KHD125/WAVE-3.0, main file wave_app.py) via the import shim.
"""

from __future__ import annotations

import io
import os
import re
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

try:  # local: alpha/ package inside the PRISM tree
    from alpha.odds import _clean, _label, brier_score, calibration_table, fit_predict_one, walk_forward
    from alpha.panel import (add_forward_returns, apply_universe_screen,
                             parse_date_from_filename, _normalize_snapshot)
    from alpha.scan import compute_features
    from alpha.track import compute_track
    from alpha.weekly import MAX_PER_SECTOR, TOP_N, UNIVERSE_CATEGORY, MODEL_VERSION
except ImportError:  # standalone: repo root (Streamlit Cloud)
    from odds import _clean, _label, brier_score, calibration_table, fit_predict_one, walk_forward
    from panel import (add_forward_returns, apply_universe_screen,
                       parse_date_from_filename, _normalize_snapshot)
    from scan import compute_features
    from track import compute_track
    from weekly import MAX_PER_SECTOR, TOP_N, UNIVERSE_CATEGORY, MODEL_VERSION

LOCAL_ARCHIVE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "Alpha Resources", "Weekly", "Stocks_Backups Weekly")

st.set_page_config(page_title="WAVE 3.0", page_icon="🌊", layout="wide")


# ── Drive loader (ported from Alpha Trajectory — proven against the same folder) ──

def _normalize_drive_key(raw: str) -> str:
    key = (raw or "").strip()
    if "drive.google.com" in key and "/folders/" in key:
        key = key.split("/folders/", 1)[1].split("?", 1)[0].split("/", 1)[0].strip()
    return key


def _load_csvs_from_drive(folder_key: str) -> Tuple[List[Tuple[str, bytes]], Optional[str]]:
    import requests

    key = _normalize_drive_key(folder_key)
    if not key:
        return [], "Folder key is empty."
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        resp = session.get(f"https://drive.google.com/drive/folders/{key}", timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return [], f"Could not open the Drive folder: {e}"

    entries = re.findall(r'\["(1[a-zA-Z0-9_-]{10,})","([^"]+\.csv)"', resp.text, re.IGNORECASE)
    if not entries:
        ids = list(dict.fromkeys(re.findall(r'/file/d/(1[a-zA-Z0-9_-]{10,})', resp.text)
                                 + re.findall(r'data-id="(1[a-zA-Z0-9_-]{10,})"', resp.text)))
        names = re.findall(r'(Stocks_Weekly[^"<>\s]*\.csv)', resp.text, re.IGNORECASE)
        entries = list(zip(ids, names)) if names else [(i, f"file_{i}.csv") for i in ids]

    seen, files = set(), []
    for fid, fname in entries:
        if fid in seen:
            continue
        seen.add(fid)
        url = f"https://drive.google.com/uc?export=download&id={fid}"
        try:
            dl = session.get(url, timeout=60)
            content = dl.content
            if b"<html" in content[:200].lower() and b"confirm=" in content:
                m = re.search(r"confirm=([0-9A-Za-z_-]+)", dl.text)
                if m:
                    content = session.get(f"{url}&confirm={m.group(1)}", timeout=90).content
            head = content[:500].decode("utf-8", errors="ignore").lower()
            if "<html" in head and "ticker" not in head:
                continue
            cd = dl.headers.get("Content-Disposition", "")
            m = re.search(r'filename="?([^";\n]+)"?', cd)
            real = m.group(1).strip() if m else fname
            if real.lower().endswith(".csv"):
                files.append((real, content))
        except Exception:
            continue
    if not files:
        return [], ("No CSVs downloaded. Check: folder sharing = 'Anyone with the link → Viewer', "
                    "and the folder holds Stocks_Weekly_*.csv files.")
    return files, None


# ── Pipeline (source-agnostic: a list of (filename, bytes) in, the table out) ──

@st.cache_data(show_spinner="Building the honest panel…", max_entries=2)
def _panel_from_files(files: List[Tuple[str, bytes]]) -> pd.DataFrame:
    frames = []
    for name, data in files:
        date = parse_date_from_filename(name)
        if date is None:
            continue
        raw = pd.read_csv(io.BytesIO(data), encoding="utf-8", low_memory=False)
        frames.append(_normalize_snapshot(raw, date))
    if not frames:
        raise ValueError("No dated Stocks_Weekly_*.csv files found.")
    panel = pd.concat(frames, ignore_index=True, sort=False)
    panel = panel.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
    panel, _report = add_forward_returns(panel, horizons_weeks=(4,))
    return apply_universe_screen(panel)


@st.cache_data(show_spinner="Training on every finished outcome…", max_entries=2)
def _forecast(panel: pd.DataFrame):
    d = _label(_clean(compute_track(compute_features(panel))))
    latest = d["date"].max()
    train = d[d["y_up"].notna()]           # only fully-realized labels — leak-proof by construction
    scored = fit_predict_one(train, d[d["date"] == latest])
    scored = scored[scored["category"] == UNIVERSE_CATEGORY]
    scored = scored.sort_values("net_edge", ascending=False, kind="mergesort")
    scored = scored[scored.groupby("sector").cumcount() < MAX_PER_SECTOR].head(TOP_N)
    meta = dict(latest=latest, trained_through=train["date"].max(),
                weeks=int(train["date"].nunique()),
                base_up=float(train["y_up"].mean()), base_dn=float(train["y_dn"].mean()))
    return scored, meta, d


# ── UI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    st.title("🌊 WAVE 3.0")
    st.caption(f"model v{MODEL_VERSION} · {UNIVERSE_CATEGORY} · top {TOP_N} by net edge · "
               f"max {MAX_PER_SECTOR}/sector · every number earned, never stated")
    st.warning("**EXPERIMENTAL** — the model failed its first calibration audit by up to +16pp "
               "(regime shift; TEST_LEDGER #53). Probabilities are the model's honest best, not "
               "settled truth. The frozen forecast log is the only judge (first review 2027-02-21).",
               icon="⚠️")

    with st.sidebar:
        st.header("Data")
        options = ["Google Drive folder", "Upload CSVs"]
        if os.path.isdir(LOCAL_ARCHIVE):
            options.insert(0, "Local archive")
        source = st.radio("Weekly snapshots from", options)
        files: List[Tuple[str, bytes]] = []
        if source == "Local archive":
            import glob
            paths = sorted(glob.glob(os.path.join(LOCAL_ARCHIVE, "*.csv")))
            st.caption(f"{len(paths)} files in the local archive")
            if st.button("Load archive", type="primary"):
                files = [(os.path.basename(p), open(p, "rb").read()) for p in paths]
        elif source == "Google Drive folder":
            key = st.text_input("Public folder link or key",
                                value=st.session_state.get("drive_key", ""))
            if st.button("Load from Drive", type="primary") and key:
                st.session_state["drive_key"] = key
                with st.spinner("Downloading weekly CSVs from Drive…"):
                    files, err = _load_csvs_from_drive(key)
                if err:
                    st.error(err)
        else:
            up = st.file_uploader("Stocks_Weekly_*.csv", type="csv", accept_multiple_files=True)
            if up and st.button("Load uploads", type="primary"):
                files = [(f.name, f.getvalue()) for f in up]
        if files:
            st.session_state["files"] = files
        st.divider()
        st.caption("Laws live in PLAN.md · tests in tests/ · every test ever run in TEST_LEDGER.md")

    if "files" not in st.session_state:
        st.info("Load the weekly snapshots from the sidebar to get this week's table.")
        st.stop()

    panel = _panel_from_files(st.session_state["files"])
    table, meta, labeled = _forecast(panel)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Snapshot", f"{meta['latest']:%d %b %Y}")
    c2.metric("Trained through", f"{meta['trained_through']:%d %b %Y}", f"{meta['weeks']} weeks")
    c3.metric("Base P(wave +15%/4w)", f"{meta['base_up']*100:.1f}%")
    c4.metric("Base P(crash −15%/4w)", f"{meta['base_dn']*100:.1f}%")

    view = table[["ticker", "company_name", "sector", "price", "p_up", "p_dn",
                  "net_edge", "persist", "sector_heat"]].copy()
    view.columns = ["Ticker", "Company", "Sector", "Price ₹", "P(wave)", "P(crash)",
                    "Net edge", "Persist (w)", "Sector heat"]
    st.dataframe(
        view.style.format({"Price ₹": "{:,.0f}", "P(wave)": "{:.1%}", "P(crash)": "{:.1%}",
                           "Net edge": "{:+.1%}", "Sector heat": "{:.2f}"})
            .background_gradient(subset=["Net edge"], cmap="Greens")
            .background_gradient(subset=["P(crash)"], cmap="Reds"),
        use_container_width=True, height=38 * (len(view) + 1),
    )
    st.download_button("⬇️ Download this table (CSV)",
                       table.to_csv(index=False).encode("utf-8"),
                       file_name=f"wave3_forecast_{meta['latest']:%Y-%m-%d}.csv")

    with st.expander("🔍 Calibration audit — does the model keep its promises? (slow, walk-forward)"):
        if st.button("Run the audit"):
            with st.spinner("Refitting the model once per historical week…"):
                oos = walk_forward(compute_track(compute_features(panel)))
            if oos.empty:
                st.info("Not enough history yet (needs 26+ training weeks).")
            else:
                st.caption(f"{oos['date'].nunique()} out-of-sample weeks · "
                           f"Brier P(wave) {brier_score(oos):.4f} · "
                           f"Brier P(crash) {brier_score(oos, 'p_dn', 'y_dn'):.4f} "
                           f"(base-rate-only would score ≈ p·(1−p))")
                a, b = st.columns(2)
                a.subheader("P(wave): stated vs actual")
                a.dataframe(calibration_table(oos).style.format("{:.3f}"), use_container_width=True)
                b.subheader("P(crash): stated vs actual")
                b.dataframe(calibration_table(oos, "p_dn", "y_dn").style.format("{:.3f}"),
                            use_container_width=True)
                st.caption("Honesty bar: |gap_pp| ≤ ~5 per decile. Fail → the model stays EXPERIMENTAL.")

    st.caption("WAVE 3.0 · the successor to Wave Detection + Alpha Trajectory · "
               "\"every idea was plausible; none was ever asked to prove itself\" — here, everything asks.")


if st.runtime.exists() or __name__ == "__main__":   # render only under `streamlit run`
    main()
