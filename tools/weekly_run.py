"""
tools/weekly_run.py — the headless Sunday run.

    python -m tools.weekly_run            # uses WAVE_DRIVE_FOLDER, else local archive

Fetches the newest weekly snapshots, scores them, prints the table, and APPENDS
the forecast to logs/waves_log.csv. Designed for CI: no Streamlit, no prompts,
non-zero exit on failure so a silent breakage can't masquerade as "no waves".

This exists because the deployed app CANNOT write the log — Streamlit Cloud has a
read-only filesystem and no push credentials. Without this, the entire
pre-registration would depend on a human remembering a command every Sunday for
26 weeks, which is a hope, not a design.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.decide import append_log, build_forecast_from_files          # noqa: E402
from core.config import DRIVE_FOLDER_WEEKLY, MODEL_VERSION, RANK_FEATURE   # noqa: E402
from core.sources import load_csvs_from_drive, local_archive_files     # noqa: E402


def collect_files():
    """Drive folder, else the on-disk archive (local runs).

    Order: env var (an override, if the folder moves) -> config -> local archive.
    Config carries a working default so CI needs no manual setup step — a step
    someone must remember is a step that eventually gets forgotten, and a weekly
    job that silently stops is the one failure this whole design exists to avoid.
    """
    key = (os.environ.get("WAVE_DRIVE_FOLDER", "").strip() or DRIVE_FOLDER_WEEKLY)
    if key:
        files, err = load_csvs_from_drive(key)
        if err:
            raise RuntimeError(f"Drive load failed: {err}")
        print(f"loaded {len(files)} CSVs from the Drive folder")
        return files
    files = local_archive_files()
    if not files:
        raise RuntimeError(
            "No data: the Drive folder returned nothing and no local archive exists.")
    print(f"loaded {len(files)} CSVs from the local archive")
    return files


def main() -> int:
    table, meta = build_forecast_from_files(collect_files())
    print(f"\nWAVE {MODEL_VERSION} · snapshot {meta['latest']:%Y-%m-%d} · trained through "
          f"{meta['trained_through']:%Y-%m-%d} · {meta['weeks']} weeks · {len(table)} names\n")
    # Columns come from LOG_COLUMNS-adjacent v3.1 fields. Never hardcode a column
    # list that core/decide.py also defines: this printed v3.0's p_up/p_dn/net_edge
    # after the v3.1 switch and would have crashed the first Sunday job.
    cols = [c for c in ("ticker", "sector", "price", RANK_FEATURE, "decile",
                        "hist_rate", "persist", "sector_heat") if c in table.columns]
    view = table[cols].copy()
    if RANK_FEATURE in view:
        view[RANK_FEATURE] = (view[RANK_FEATURE] * 100).round(0)
    if "hist_rate" in view:
        view["hist_rate"] = (view["hist_rate"] * 100).round(1)
    print(view.to_string(index=False))
    if append_log(table):
        print(f"\nfrozen to logs/waves_log.csv — {len(table)} rows appended")
    else:
        print(f"\nsnapshot {meta['latest']:%Y-%m-%d} already logged — nothing appended. "
              "A retried or manually re-dispatched run must not double-count the "
              "sample the verdict is computed from.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                      # CI must fail loudly, never quietly
        print(f"WEEKLY RUN FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
