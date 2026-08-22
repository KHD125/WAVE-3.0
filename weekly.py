"""
alpha.weekly — Stage 4 of WAVE 3.0 (see alpha/PLAN.md §4): the Sunday table.

    python -m alpha.weekly

Rebuilds the panel from the archive, trains on every week whose 4-week label is
already realized (so the live model never touches an unfinished outcome), scores
the NEWEST snapshot, prints the Mid Cap top-30 by net edge, and appends the full
table to alpha/waves_log.csv.

THE LOG IS THE EXPERIMENT (Law 9). Rows are appended, timestamped, and never
edited — in six months the frozen forecasts face reality with no room to narrate.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from alpha.odds import MODEL_FEATURES, _clean, _label, fit_predict_one
from alpha.panel import build_panel
from alpha.scan import compute_features
from alpha.track import compute_track

ARCHIVE = os.path.join("alpha", "Alpha Resources", "Weekly", "Stocks_Backups Weekly")
LOG = os.path.join("alpha", "waves_log.csv")
TOP_N = 30
MAX_PER_SECTOR = 3            # the seatbelt (PLAN §5) — not tunable
UNIVERSE_CATEGORY = "Mid Cap"
MODEL_VERSION = "3.0"


def build_forecast() -> pd.DataFrame:
    panel, report = build_panel(ARCHIVE, horizons_weeks=(4,))
    panel = compute_track(compute_features(panel))
    d = _label(_clean(panel))

    latest = d["date"].max()
    week = d[d["date"] == latest]
    # Train ONLY where the 4-week outcome is fully known — automatic no-leakage:
    # labels stop existing 4 weeks before `latest`, so the embargo is structural.
    train = d[d["y_up"].notna()]
    scored = fit_predict_one(train, week)

    scored = scored[scored["category"] == UNIVERSE_CATEGORY]
    scored = scored.sort_values("net_edge", ascending=False, kind="mergesort")
    scored = scored[scored.groupby("sector").cumcount() < MAX_PER_SECTOR].head(TOP_N)
    scored["snapshot_date"] = latest
    scored["trained_through"] = train["date"].max()
    scored["model_version"] = MODEL_VERSION
    scored["logged_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return scored


def append_log(table: pd.DataFrame) -> None:
    cols = ["logged_at_utc", "model_version", "snapshot_date", "trained_through",
            "ticker", "sector", "price", "p_up", "p_dn", "net_edge", "persist",
            "sector_heat", "p_range_pos"]
    row = table[cols].copy()
    header = not os.path.exists(LOG)
    row.to_csv(LOG, mode="a", header=header, index=False)   # append-only, never rewrite


def main() -> None:
    t = build_forecast()
    latest = t["snapshot_date"].iloc[0]
    print(f"WAVE 3.0 · snapshot {latest:%Y-%m-%d} · trained through "
          f"{t['trained_through'].iloc[0]:%Y-%m-%d} · {UNIVERSE_CATEGORY} · "
          f"top {len(t)} by net edge (max {MAX_PER_SECTOR}/sector)")
    print()
    view = t[["ticker", "sector", "price", "p_up", "p_dn", "net_edge",
              "persist", "sector_heat"]].copy()
    view["p_up"] = (view["p_up"] * 100).round(1)
    view["p_dn"] = (view["p_dn"] * 100).round(1)
    view["net_edge"] = (view["net_edge"] * 100).round(1)
    view["sector_heat"] = view["sector_heat"].round(2)
    view.columns = ["ticker", "sector", "price", "P(wave)%", "P(crash)%",
                    "edge_pp", "persist_w", "sect_heat"]
    print(view.to_string(index=False))
    append_log(t)
    print()
    print(f"frozen to {LOG} — the log is the experiment; it is never edited.")


if __name__ == "__main__":
    main()
