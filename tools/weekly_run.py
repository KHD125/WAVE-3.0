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
from core.sources import load_csvs_from_drive, local_archive_files     # noqa: E402


def collect_files():
    """Drive folder if configured, else the on-disk archive (local runs)."""
    key = os.environ.get("WAVE_DRIVE_FOLDER", "").strip()
    if key:
        files, err = load_csvs_from_drive(key)
        if err:
            raise RuntimeError(f"Drive load failed: {err}")
        print(f"loaded {len(files)} CSVs from the Drive folder")
        return files
    files = local_archive_files()
    if not files:
        raise RuntimeError(
            "No data. Set WAVE_DRIVE_FOLDER (repo variable) or provide a local archive.")
    print(f"loaded {len(files)} CSVs from the local archive")
    return files


def main() -> int:
    table, meta = build_forecast_from_files(collect_files())
    print(f"\nWAVE 3.0 · snapshot {meta['latest']:%Y-%m-%d} · trained through "
          f"{meta['trained_through']:%Y-%m-%d} · {meta['weeks']} weeks · {len(table)} names\n")
    view = table[["ticker", "sector", "price", "p_up", "p_dn", "net_edge", "persist"]].copy()
    for c in ("p_up", "p_dn", "net_edge"):
        view[c] = (view[c] * 100).round(1)
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
