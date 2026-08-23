"""
core.sources — where weekly snapshots come from. Three doors, one output shape:
a list of (filename, bytes), which build_panel_from_files turns into the honest
panel. Keeping acquisition here means app.py stays a display surface and the
engine never learns where its data happened to come from.

  local_archive_files()      the home machine's backup folder
  load_csvs_from_drive()     the public Google Drive backup folder (loader ported
                             from Alpha Trajectory's proven implementation)
  build_panel_from_files()   (name, bytes) -> panel with forward returns + screen
"""

from __future__ import annotations

import glob
import io
import os
import re
import time
from typing import List, Optional, Tuple

import logging

import pandas as pd

from .panel import (add_forward_returns, apply_universe_screen,
                    parse_date_from_filename, _normalize_snapshot)

logger = logging.getLogger(__name__)

# Drive throttles bursts of ~50 downloads and returns an HTML notice instead of the
# file. Measured transient (a repeat run fetched all 50 cleanly), so pace and retry
# rather than failing the weekly job on a blip.
RETRY_ATTEMPTS = 3
PACE_SECONDS = 0.15
BACKOFF_SECONDS = 1.5

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_ARCHIVE = os.path.join(_ROOT, "Alpha Resources", "Weekly", "Stocks_Backups Weekly")

FileBytes = Tuple[str, bytes]


def local_archive_files() -> List[FileBytes]:
    """Every dated CSV in the on-disk archive (empty list on Streamlit Cloud)."""
    paths = sorted(glob.glob(os.path.join(LOCAL_ARCHIVE, "*.csv")))
    return [(os.path.basename(p), open(p, "rb").read()) for p in paths]


def build_panel_from_files(files: List[FileBytes],
                           horizons_weeks: Tuple[int, ...] = (4,)) -> pd.DataFrame:
    """(filename, bytes) -> the stage-0 panel. Same laws as panel.build_panel."""
    frames, skipped = [], []
    for name, data in files:
        date = parse_date_from_filename(name)
        if date is None:
            skipped.append((name, "no date in filename"))
            continue
        try:
            raw = pd.read_csv(io.BytesIO(data), encoding="utf-8", low_memory=False)
            if "ticker" not in raw.columns:
                # A live #REF!/#N/A in the sheet gets frozen into the backup and
                # renames the key column (seen: Stocks_Daily_2026-04-22, header
                # '#REF!'). One corrupt snapshot must not kill the run — but it
                # must be REPORTED. A silently dropped week is a hole in the
                # evidence that nothing downstream can see.
                raise ValueError(f"no 'ticker' column (found {list(raw.columns)[:3]})")
            frames.append(_normalize_snapshot(raw, date))
        except Exception as exc:
            skipped.append((name, f"{type(exc).__name__}: {exc}"))
    if skipped:
        logger.warning("SKIPPED %d unreadable snapshot(s):", len(skipped))
        for name, why in skipped:
            logger.warning("   %s  ->  %s", name, why)
    if not frames:
        raise ValueError("No usable dated snapshots found.")
    panel = pd.concat(frames, ignore_index=True, sort=False)
    panel = panel.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
    panel, _report = add_forward_returns(panel, horizons_weeks=horizons_weeks)
    return apply_universe_screen(panel)


# ── Google Drive public-folder loader ─────────────────────────────────────────

def normalize_drive_key(raw: str) -> str:
    key = (raw or "").strip()
    if "drive.google.com" in key and "/folders/" in key:
        key = key.split("/folders/", 1)[1].split("?", 1)[0].split("/", 1)[0].strip()
    return key


# The /drive/folders/ page embeds only the FIRST ~50 entries; the rest arrive by
# scroll, which a scraper never triggers. That cap does not look like an error — it
# looks like a folder that stopped receiving files. It cost a real diagnosis: a
# folder holding 53 weekly snapshots reported 50, the three NEWEST were the ones
# dropped, and the conclusion drawn was "the upstream backup has stalled since
# 2026-08-02" when nothing had stalled at all. A silent cap that presents as stale
# data is worse than a crash.
#
# embeddedfolderview returns the whole listing as plain HTML with no JS. Both are
# read and UNIONED by file id, so neither one's blind spot can hide a week.
_EMBED_URL = "https://drive.google.com/embeddedfolderview?id={key}#list"
# Pair id and title WITHIN one entry block. Two separate findalls would zip by
# position across independent scans and mislabel every file if the orders differ.
_EMBED_ENTRY = re.compile(
    r'/file/d/([a-zA-Z0-9_-]{20,}).*?flip-entry-title[^>]*>([^<]+)<', re.S)
_PAGE_ENTRY = re.compile(r'\["(1[a-zA-Z0-9_-]{10,})","([^"]+\.csv)"', re.IGNORECASE)


def _list_folder(session, key: str, page_html: str) -> List[Tuple[str, str]]:
    """Every (file_id, filename) in a public folder, from BOTH listings."""
    found: dict = {}
    try:
        embed = session.get(_EMBED_URL.format(key=key), timeout=60).text
        for fid, name in _EMBED_ENTRY.findall(embed):
            name = name.strip()
            if name.lower().endswith(".csv"):
                found[fid] = name
    except Exception as exc:                     # fall back, never fail the run
        logger.warning("embeddedfolderview listing failed: %s", exc)

    page = {fid: name for fid, name in _PAGE_ENTRY.findall(page_html)}
    if not page:
        ids = dict.fromkeys(re.findall(r'/file/d/(1[a-zA-Z0-9_-]{10,})', page_html)
                            + re.findall(r'data-id="(1[a-zA-Z0-9_-]{10,})"', page_html))
        page = {i: f"file_{i}.csv" for i in ids}
    for fid, name in page.items():
        found.setdefault(fid, name)

    if len(found) > len(page) and page:
        logger.info("folder page listed %d of %d files (it caps at ~50); "
                    "embeddedfolderview supplied the rest", len(page), len(found))
    return sorted(found.items(), key=lambda kv: kv[1])


def load_csvs_from_drive(folder_key: str) -> Tuple[List[FileBytes], Optional[str]]:
    """Download every CSV from a public Drive folder. Returns (files, error)."""
    import requests

    key = normalize_drive_key(folder_key)
    if not key:
        return [], "Folder key is empty."
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        resp = session.get(f"https://drive.google.com/drive/folders/{key}", timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return [], f"Could not open the Drive folder: {e}"

    entries = _list_folder(session, key, resp.text)

    seen, files, failed = set(), [], []
    for fid, fname in entries:
        if fid in seen:
            continue
        seen.add(fid)
        url = f"https://drive.google.com/uc?export=download&id={fid}"
        last_error = None
        # Drive throttles ~50 rapid downloads and answers with an HTML notice, not
        # a CSV. Verified transient: an identical second run fetched all 50 cleanly.
        # So pace the requests and back off — a Sunday job that fails on a blip
        # leaves a hole in the log, which is worse than the blip.
        time.sleep(PACE_SECONDS)
        for attempt in range(RETRY_ATTEMPTS):
            try:
                dl = session.get(url, timeout=60)
                content = dl.content
                if b"<html" in content[:200].lower() and b"confirm=" in content:
                    m = re.search(r"confirm=([0-9A-Za-z_-]+)", dl.text)
                    if m:
                        content = session.get(f"{url}&confirm={m.group(1)}",
                                              timeout=90).content
                head = content[:500].decode("utf-8", errors="ignore").lower()
                if "<html" in head and "ticker" not in head:
                    # Ambiguous: an unshared file AND a throttle notice both look
                    # like HTML. RAISE rather than `continue` — continue would skip
                    # the backoff at the loop foot, retrying instantly against the
                    # very throttle that needs time to clear. A throttle clears; a
                    # sharing problem does not, and the final error names the file.
                    raise ValueError("received HTML, not CSV (throttled, or not shared)")
                cd = dl.headers.get("Content-Disposition", "")
                m = re.search(r'filename="?([^";\n]+)"?', cd)
                real = m.group(1).strip() if m else fname
                if real.lower().endswith(".csv"):
                    files.append((real, content))
                last_error = None
                break
            except Exception as exc:
                last_error = (str(exc) if isinstance(exc, ValueError)
                              else f"{type(exc).__name__}: {exc}")
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(BACKOFF_SECONDS * (attempt + 1))
        if last_error:
            failed.append((fname, last_error))

    if not files:
        return [], ("No CSVs downloaded. Check: folder sharing = 'Anyone with the link → "
                    "Viewer', and the folder holds Stocks_Weekly_*.csv files.")
    if failed:
        # PARTIAL downloads must NOT pass silently. For the app a missing week is
        # an annoyance; for a forecast about to be frozen into the permanent log
        # it is corruption — the odds would be computed on incomplete history and
        # nothing downstream could ever tell. Callers decide: app.py warns and
        # continues, tools/weekly_run.py treats any error as fatal.
        detail = "; ".join(f"{n} ({why})" for n, why in failed[:5])
        logger.warning("Drive: %d of %d files failed to download", len(failed),
                       len(files) + len(failed))
        return files, (f"Downloaded {len(files)} files but {len(failed)} FAILED: {detail}"
                       + (" …" if len(failed) > 5 else ""))
    return files, None
