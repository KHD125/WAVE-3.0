"""
core.decide — Stage 4 of WAVE 3.0 (see docs/PLAN.md §4): the Sunday table.

    python -m core.decide          # local archive
    python -m tools.weekly_run     # CI / Drive folder, then commits the log

Trains on every week whose 4-week label is already realized (so the live model
never touches an unfinished outcome), scores the NEWEST snapshot, and appends the
top-N table to logs/waves_log.csv.

THE LOG IS THE EXPERIMENT (Law 9). Rows are appended, timestamped, and never
edited — in six months the frozen forecasts face reality with no room to narrate.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, Tuple

import pandas as pd

from .config import (MAX_PER_SECTOR, MODEL_VERSION, RANK_FEATURE, TOP_N,
                     UNIVERSE_CATEGORIES)
from .counted import attach_counted_odds
from .odds import _clean, _label
from .scan import compute_features
from .track import compute_track

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(_ROOT, "Alpha Resources", "Weekly", "Stocks_Backups Weekly")
LOG = os.path.join(_ROOT, "logs", "waves_log.csv")

LOG_COLUMNS = ["logged_at_utc", "model_version", "snapshot_date", "trained_through",
               "ticker", "company_name", "sector", "category", "price",
               "p_range_pos", "decile", "hist_rate", "hist_n",
               "persist", "sector_heat", "from_high"]


def score_panel(panel: pd.DataFrame) -> Tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Panel in -> (top-N table, meta, full scored frame). The single scoring path.

    app.py, core.decide and tools.weekly_run ALL route through this, so a change
    to selection can never apply to one surface and not another — the failure
    that let Wave Detection's ranking mean something different in each tab.

    Returns the FULL scored frame as well, so callers never recompute the feature
    pipeline to get it (app.py did, doubling the work on every cache miss).
    """
    d = _label(_clean(compute_track(compute_features(panel))))
    if d.empty:
        raise ValueError("No investable rows after screening — check the snapshots.")
    latest = d["date"].max()
    # Train ONLY where the 4-week outcome is fully known. Labels stop existing
    # 4 weeks before `latest`, so the embargo is structural, not a parameter.
    train = d[d["y_up"].notna()]
    if train.empty:
        raise ValueError("No resolved labels — need at least 4 weeks of history.")

    # v3.1: rank by ONE measured column. No model, no fitted parameters.
    week = attach_counted_odds(d[d["date"] == latest], train)
    table = week[week["category"].isin(UNIVERSE_CATEGORIES)].sort_values(
        RANK_FEATURE, ascending=False, kind="mergesort")
    table = table[table.groupby("sector").cumcount() < MAX_PER_SECTOR].head(TOP_N)

    meta = {
        "latest": latest,
        "trained_through": train["date"].max(),
        "weeks": int(train["date"].nunique()),
        "base_up": float(train["y_up"].mean()),
        "base_dn": float(train["y_dn"].mean()),
        "universe": int(len(week)),
    }
    # Attach this week's probabilities back onto the full frame so the UI can
    # show odds beside every historical row without a second merge upstream.
    scored = d.merge(week[["ticker", "date", "decile", "hist_rate", "hist_lift",
                           "hist_n", "hist_base"]], on=["ticker", "date"], how="left")
    return table, meta, scored


def _stamp(table: pd.DataFrame, meta: dict) -> pd.DataFrame:
    out = table.copy()
    out["snapshot_date"] = meta["latest"]
    out["trained_through"] = meta["trained_through"]
    out["model_version"] = MODEL_VERSION
    out["logged_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return out


def build_forecast_from_files(files) -> Tuple[pd.DataFrame, dict]:
    """(filename, bytes) -> stamped top-N table + meta. Used by CI and the Drive path."""
    from .sources import build_panel_from_files
    table, meta, _scored = score_panel(build_panel_from_files(files))
    return _stamp(table, meta), meta


def build_forecast() -> Tuple[pd.DataFrame, dict]:
    """Same, from the on-disk archive."""
    from .panel import build_panel
    panel, _report = build_panel(ARCHIVE, horizons_weeks=(4,))
    table, meta, _scored = score_panel(panel)
    return _stamp(table, meta), meta


def append_log(table: pd.DataFrame, path: Optional[str] = None) -> bool:
    """Append this snapshot's forecast. Returns False if it was already logged.

    Append-only: existing rows are NEVER rewritten — a corrected log is not a log.
    But a snapshot already present is REFUSED rather than duplicated. A weekly job
    that gets re-run (a retry, a manual dispatch, a redeploy) would otherwise
    double-count the same forecast and quietly inflate the sample the February
    verdict is computed from.

    `path=None` resolves the module-level LOG at CALL time, deliberately. Writing
    `path: str = LOG` binds the default at DEFINITION time, so a test that
    monkeypatches decide.LOG still writes to the real log — which is exactly what
    happened, and it corrupted the frozen experiment record until git restored it.
    A test must never be able to reach production data.
    """
    path = path or LOG
    os.makedirs(os.path.dirname(path), exist_ok=True)
    snapshot = pd.to_datetime(table["snapshot_date"].iloc[0])
    version = str(table["model_version"].iloc[0])
    if os.path.exists(path):
        # SCHEMA GUARD. A CSV append writes no header, so appending 16-column rows
        # under a 13-column header silently corrupts the file — every later read
        # dies with a tokenizing error, and the experiment record is gone unless
        # git has it. A version bump that changes LOG_COLUMNS must ARCHIVE the old
        # log and start a new one, never append across schemas.
        header = pd.read_csv(path, nrows=0).columns.tolist()
        if header != LOG_COLUMNS:
            raise ValueError(
                f"log schema mismatch: {path} has {len(header)} columns, the code "
                f"writes {len(LOG_COLUMNS)}. Appending would corrupt it. Archive the "
                f"old log (e.g. logs/waves_log_v<old>.csv) and let a fresh one start.\n"
                f"  on disk: {header}\n  in code: {LOG_COLUMNS}")
        # Key on (snapshot_date, model_version), NOT snapshot_date alone. A new
        # model version forecasting the same week is a genuinely DIFFERENT forecast
        # and February grades the versions separately — keying on the date alone
        # let a v3.0 row block v3.1 entirely, silently costing the new version its
        # first week of evidence.
        existing = pd.read_csv(path, usecols=["snapshot_date", "model_version"])
        same = (pd.to_datetime(existing["snapshot_date"], errors="coerce") == snapshot) & \
               (existing["model_version"].astype(str) == version)
        if same.any():
            return False
    table.reindex(columns=LOG_COLUMNS).to_csv(
        path, mode="a", header=not os.path.exists(path), index=False)
    return True


def main() -> None:
    table, meta = build_forecast()
    print(f"WAVE {MODEL_VERSION} · snapshot {meta['latest']:%Y-%m-%d} · trained through "
          f"{meta['trained_through']:%Y-%m-%d} · {' + '.join(UNIVERSE_CATEGORIES)} · "
          f"top {len(table)} by range_pos (max {MAX_PER_SECTOR}/sector)")
    print()
    view = table[["ticker", "sector", "price", RANK_FEATURE, "decile",
                  "hist_rate", "persist", "sector_heat"]].copy()
    view[RANK_FEATURE] = (view[RANK_FEATURE] * 100).round(0)
    view["hist_rate"] = (view["hist_rate"] * 100).round(1)
    view["sector_heat"] = view["sector_heat"].round(2)
    view.columns = ["ticker", "sector", "price", "range_pos_pct", "decile",
                    "hist_wave%", "persist_w", "sect_heat"]
    print(view.to_string(index=False))
    # Report what actually happened. Printing "frozen" unconditionally would
    # announce success for a write that was refused — the precise failure mode
    # this whole project exists to eliminate.
    if append_log(table):
        print(f"\nfrozen to {LOG} — the log is the experiment; it is never edited.")
    else:
        print(f"\nsnapshot {meta['latest']:%Y-%m-%d} is ALREADY logged — nothing "
              "appended. A re-run must not double-count the sample the verdict "
              "is computed from.")


if __name__ == "__main__":
    main()
