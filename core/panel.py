"""
alpha.panel — the canonical price/factor panel.

This module is the FOUNDATION of the alpha engine. Nothing above it means anything
unless the forward returns here are honest, so this file has exactly one job:

    turn N dated snapshot CSVs into a long panel keyed (ticker, date),
    with forward returns that do not lie.

HARD RULES (see CLAUDE.md §8):
  * Forward returns join on the ACTUAL next snapshot date, never on a row index.
    `groupby(ticker).shift(-k)` silently reaches k snapshots forward even when a
    ticker missed a week, mislabelling a 2-week return as a 1-week return.
  * A ticker that DISAPPEARS is a fact, not a filter. It is marked, counted and
    reported — never silently dropped. Dropping it is how a backtest quietly
    deletes its own losses.
  * Corporate actions are DETECTED and FLAGGED, never silently absorbed. An
    unadjusted 1:5 split reads as a -80% week and poisons every mean it touches.
  * No sentinel values. Missing stays NaN all the way through.

The source CSVs are Indian-formatted strings, not numbers:
    market_cap  '₹12,987 Cr'      price '₹1,091'      from_low_pct '46.36%'
Read them with `encoding='utf-8'` — cp1252 cannot represent ₹.
"""

from __future__ import annotations

import glob
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Column groups by the format they arrive in ────────────────────────────────
# Rupee-denominated levels: '₹1,091' -> 1091.0
CURRENCY_COLUMNS: Tuple[str, ...] = (
    "price", "low_52w", "high_52w", "sma_20d", "sma_50d", "sma_200d", "prev_close",
)
# Percentages: '46.36%' -> 46.36  (kept in PERCENT units, not fractions)
PERCENT_COLUMNS: Tuple[str, ...] = (
    "from_low_pct", "from_high_pct",
    "ret_1d", "ret_3d", "ret_7d", "ret_30d", "ret_3m", "ret_6m", "ret_1y", "ret_3y", "ret_5y",
    "vol_ratio_1d_90d", "vol_ratio_7d_90d", "vol_ratio_30d_90d",
    "vol_ratio_1d_180d", "vol_ratio_7d_180d", "vol_ratio_30d_180d", "vol_ratio_90d_180d",
    "eps_change_pct",
)
# Plain counts that may still carry thousands separators
COUNT_COLUMNS: Tuple[str, ...] = (
    "volume_1d", "volume_7d", "volume_30d", "volume_90d", "volume_180d",
)
# Already numeric in the source
NUMERIC_COLUMNS: Tuple[str, ...] = ("rvol", "pe", "eps_current", "eps_last_qtr", "year")
# Carried through untouched
STRING_COLUMNS: Tuple[str, ...] = ("ticker", "company_name", "category", "sector", "industry")

# Locked thresholds live in core/config.py — panel re-exports CRORE for callers.
from .config import CRORE, MIN_MARKET_CAP, MIN_PRICE, MIN_TURNOVER  # noqa: E402

# A weekly move beyond this is treated as SUSPECT and checked against the 52w
# levels for a corporate action. Chosen well above genuine weekly volatility
# (the 99.9th percentile of Indian weekly returns sits near 35%).
CORPORATE_ACTION_THRESHOLD_PCT = 40.0
# Ratios a split/bonus typically produces. Matched within RATIO_TOLERANCE.
COMMON_SPLIT_RATIOS: Tuple[float, ...] = (2.0, 2.5, 3.0, 4.0, 5.0, 10.0)
RATIO_TOLERANCE = 0.04

_DATE_IN_FILENAME = re.compile(r"(\d{4}-\d{2}-\d{2})")
# Strips ₹, thousands separators, %, and the ' Cr' magnitude suffix.
_STRIP_NON_NUMERIC = re.compile(r"[^0-9eE.\-+]")


def parse_date_from_filename(filename: str) -> Optional[pd.Timestamp]:
    """Extract the snapshot date from `Stocks_Weekly_YYYY-MM-DD_*.csv`."""
    match = _DATE_IN_FILENAME.search(os.path.basename(filename))
    return pd.Timestamp(match.group(1)) if match else None


def parse_indian_numeric(values: pd.Series, scale: float = 1.0) -> pd.Series:
    """
    Vectorized parse of '₹12,987 Cr' / '46.36%' / '1,091' into float.

    Returns NaN — never 0 — for anything unparseable, so that missing data stays
    distinguishable from a genuine zero downstream.
    """
    if pd.api.types.is_numeric_dtype(values):
        return values.astype(float) * scale
    cleaned = values.astype(str).str.replace(_STRIP_NON_NUMERIC, "", regex=True)
    return pd.to_numeric(cleaned.replace("", np.nan), errors="coerce") * scale


@dataclass
class PanelReport:
    """What the loader saw. Printed by every caller — silence is how bias hides."""

    n_files: int = 0
    n_rows: int = 0
    n_tickers: int = 0
    date_min: Optional[pd.Timestamp] = None
    date_max: Optional[pd.Timestamp] = None
    delistings: int = 0
    corporate_actions: int = 0
    suspect_unexplained: int = 0
    horizons: List[int] = field(default_factory=list)
    coverage: Dict[int, float] = field(default_factory=dict)

    def render(self) -> str:
        lines = [
            "── panel ──────────────────────────────────────────────",
            f"  files            {self.n_files}",
            f"  rows             {self.n_rows:,}  ({self.n_tickers:,} tickers)",
            f"  span             {self.date_min:%Y-%m-%d} → {self.date_max:%Y-%m-%d}",
            f"  delistings       {self.delistings}  (marked, NOT dropped)",
            f"  corp. actions    {self.corporate_actions}  (split/bonus detected)",
            f"  suspect moves    {self.suspect_unexplained}  (>{CORPORATE_ACTION_THRESHOLD_PCT:.0f}%, unexplained)",
        ]
        for k in self.horizons:
            lines.append(f"  fwd_ret_{k}w       {self.coverage.get(k, 0.0):5.1f}% coverage")
        lines.append("───────────────────────────────────────────────────────")
        return "\n".join(lines)


def load_snapshots(folder: str, pattern: str = "*.csv") -> pd.DataFrame:
    """
    Read every dated CSV in `folder` into one long panel keyed (ticker, date).

    Files without a parseable date are skipped and logged — a snapshot we cannot
    place in time is worse than no snapshot.
    """
    paths = sorted(glob.glob(os.path.join(folder, pattern)))
    if not paths:
        raise FileNotFoundError(f"No CSVs matching {pattern!r} in {folder!r}")

    frames: List[pd.DataFrame] = []
    for path in paths:
        date = parse_date_from_filename(path)
        if date is None:
            logger.warning("Skipping undated file: %s", os.path.basename(path))
            continue
        raw = pd.read_csv(path, encoding="utf-8", low_memory=False)
        frames.append(_normalize_snapshot(raw, date))

    if not frames:
        raise ValueError(f"No dated CSVs found in {folder!r}")

    panel = pd.concat(frames, ignore_index=True, sort=False)
    panel = panel.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
    logger.info("Loaded %d snapshots -> %d rows", len(frames), len(panel))
    return panel


def _nearest_target_dates(
    dates: pd.Index, weeks: int, tolerance_days: int = 3
) -> pd.Series:
    """
    Map each snapshot date -> the snapshot nearest to (date + `weeks` × 7 days).

    Returns NaT when the nearest snapshot is further than `tolerance_days` away
    (including past the end of the sample), so a horizon is never silently
    stretched or compressed to fit whatever snapshot happens to exist.
    """
    arr = np.asarray(dates, dtype="datetime64[D]")
    wanted = arr + np.timedelta64(weeks * 7, "D")

    right = np.searchsorted(arr, wanted)
    left = np.clip(right - 1, 0, len(arr) - 1)
    right = np.clip(right, 0, len(arr) - 1)

    dist_left = np.abs((arr[left] - wanted).astype("timedelta64[D]").astype(int))
    dist_right = np.abs((arr[right] - wanted).astype("timedelta64[D]").astype(int))
    pick = np.where(dist_left <= dist_right, left, right)
    best = np.where(dist_left <= dist_right, dist_left, dist_right)

    chosen = arr[pick].astype("datetime64[ns]")
    # A forward horizon must land strictly in the future, within tolerance.
    ok = (best <= tolerance_days) & (arr[pick] > arr)
    return pd.Series(np.where(ok, chosen, np.datetime64("NaT")), index=dates)


def _normalize_snapshot(raw: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    """Parse one snapshot's Indian-formatted columns into real numbers."""
    out = pd.DataFrame(index=raw.index)
    out["date"] = date

    for col in STRING_COLUMNS:
        if col in raw.columns:
            out[col] = raw[col].astype(str).str.strip()
    for col in CURRENCY_COLUMNS + COUNT_COLUMNS + PERCENT_COLUMNS + NUMERIC_COLUMNS:
        if col in raw.columns:
            out[col] = parse_indian_numeric(raw[col])
    if "market_cap" in raw.columns:
        # '₹12,987 Cr' — the magnitude suffix is stripped by the regex, so the
        # bare number is in crore. Store rupees so every cash figure shares units.
        out["market_cap"] = parse_indian_numeric(raw["market_cap"], scale=CRORE)

    out = out[out["ticker"].notna() & out["ticker"].ne("") & out["ticker"].ne("nan")]
    return out.drop_duplicates(subset="ticker", keep="last")


def add_forward_returns(
    panel: pd.DataFrame,
    horizons_weeks: Tuple[int, ...] = (1, 2, 4, 8),
    delisting_return_pct: float = -100.0,
) -> Tuple[pd.DataFrame, PanelReport]:
    """
    Attach `fwd_ret_{k}w` for each horizon, joined on the ACTUAL k-th next
    snapshot date rather than on a row offset.

    A ticker present at t but absent at t+k is a DELISTING: it receives
    `delisting_return_pct` (default -100%) rather than NaN, because treating a
    vanished stock as "no data" is what silently deletes a backtest's losses.
    Set to np.nan only if you have independently confirmed the disappearances
    are data gaps rather than failures.
    """
    panel = panel.copy()
    dates = pd.Index(sorted(panel["date"].unique()))
    report = PanelReport(
        n_files=len(dates),
        n_rows=len(panel),
        n_tickers=panel["ticker"].nunique(),
        date_min=dates.min(),
        date_max=dates.max(),
        horizons=list(horizons_weeks),
    )

    # date -> the snapshot nearest to (date + k weeks) ON THE CALENDAR.
    # NOT `dates.shift(-k)`: that assumes one snapshot == one week, and this
    # archive contains 8-, 6- and 1-day gaps (a duplicated snapshot on
    # 2026-04-25/26). Index-shifting would silently label a 7-week return as
    # 8-week for every date after the duplicate.
    for k in horizons_weeks:
        panel[f"_target_{k}"] = panel["date"].map(_nearest_target_dates(dates, k))

    prices = panel[["ticker", "date", "price"]].rename(
        columns={"date": "_target", "price": "_future_price"}
    )
    current = panel["price"].to_numpy(dtype=float)
    # Guarded denominator — never divide by a zero or missing base price.
    valid_base = np.isfinite(current) & (current > 0.0)
    safe_base = np.where(valid_base, current, np.nan)

    for k in horizons_weeks:
        merged = panel[["ticker", f"_target_{k}"]].rename(columns={f"_target_{k}": "_target"})
        future = merged.merge(prices, on=["ticker", "_target"], how="left")["_future_price"]
        future = future.to_numpy(dtype=float)

        has_future = np.isfinite(future) & (future > 0.0)
        fwd = np.where(valid_base & has_future, (future / safe_base - 1.0) * 100.0, np.nan)

        # A missing future price WITH a real target date means the ticker left
        # the universe: a delisting, not a data gap. Past the end of the sample
        # the target date is NaT and the outcome is genuinely unknowable -> NaN.
        target_exists = panel[f"_target_{k}"].notna().to_numpy()
        vanished = target_exists & ~has_future & valid_base
        fwd = np.where(vanished, delisting_return_pct, fwd)

        panel[f"fwd_ret_{k}w"] = fwd
        if k == min(horizons_weeks):
            report.delistings = int(vanished.sum())
        report.coverage[k] = float(np.isfinite(fwd).mean() * 100.0)

    panel = panel.drop(columns=[f"_target_{k}" for k in horizons_weeks])
    panel, report = _flag_corporate_actions(panel, report)
    return panel, report


def _flag_corporate_actions(
    panel: pd.DataFrame, report: PanelReport
) -> Tuple[pd.DataFrame, PanelReport]:
    """
    Mark weeks whose 1-week move is too large to be a genuine price move.

    THE DISCRIMINATOR: a vendor-adjusted split/bonus rescales `price` AND BOTH
    52-week levels by the same factor. Nothing else does.

        1:5 split   price ×0.2   high_52w ×0.2   low_52w ×0.2   -> corporate action
        -60% crash  price ×0.4   high_52w ×1.0   low_52w  ~new  -> a REAL loss
        +83% spike  price ×1.8   high_52w ×1.8   low_52w ×1.0   -> a REAL gain

    Matching on the price ratio alone is not enough and is actively dangerous:
    a -60% crash has ratio 0.4, whose inverse is 2.5 — a "common split ratio".
    Discarding it would re-introduce the survivorship bug wearing a new hat.
    Requiring the LOW to move too also rejects the spike case, where a stock
    breaking to new highs drags `high_52w` proportionally but never `low_52w`.
    """
    panel["is_corporate_action"] = False
    panel["is_suspect_move"] = False

    dates_all = pd.Index(sorted(panel["date"].unique()))
    if "fwd_ret_1w" in panel.columns:
        fwd = panel["fwd_ret_1w"].to_numpy(dtype=float)
    else:
        # Detection is defined on the 1-week move and must not depend on which
        # horizons the caller happened to request. Building with horizons
        # (4,8,13,26) previously skipped this silently and let every split
        # through unflagged.
        nxt = panel["date"].map(_nearest_target_dates(dates_all, 1))
        future_px = panel[["ticker"]].assign(_target=nxt).merge(
            panel[["ticker", "date", "price"]].rename(
                columns={"date": "_target", "price": "_future"}),
            on=["ticker", "_target"], how="left",
        )["_future"].to_numpy(dtype=float)
        base = panel["price"].to_numpy(dtype=float)
        ok = np.isfinite(base) & (base > 0.0)
        fwd = np.where(ok, (future_px / np.where(ok, base, np.nan) - 1.0) * 100.0, np.nan)
    suspect = np.isfinite(fwd) & (np.abs(fwd) > CORPORATE_ACTION_THRESHOLD_PCT)
    if not suspect.any():
        return panel, report

    price_ratio = 1.0 + fwd / 100.0
    levels_rescaled = np.ones(len(panel), dtype=bool)
    # Calendar-nearest, NOT dates.shift(-1) — the archive has 1-, 6- and 8-day
    # gaps, so the next snapshot is not always the next week.
    next_date = panel["date"].map(_nearest_target_dates(dates_all, 1))

    for level in ("high_52w", "low_52w"):
        if level not in panel.columns:
            # Cannot corroborate without the levels -> refuse to call it a split.
            return panel, report
        future = panel[["ticker"]].assign(_target=next_date).merge(
            panel[["ticker", "date", level]].rename(columns={"date": "_target", level: "_future"}),
            on=["ticker", "_target"], how="left",
        )["_future"].to_numpy(dtype=float)
        current = panel[level].to_numpy(dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            level_ratio = np.where(np.isfinite(current) & (current > 0.0), future / current, np.nan)
        levels_rescaled &= np.isclose(level_ratio, price_ratio, rtol=RATIO_TOLERANCE, equal_nan=False)

    corporate_action = suspect & levels_rescaled
    panel["is_corporate_action"] = corporate_action
    panel["is_suspect_move"] = suspect & ~corporate_action
    report.corporate_actions = int(corporate_action.sum())
    report.suspect_unexplained = int(panel["is_suspect_move"].sum())
    return panel, report


def apply_universe_screen(
    panel: pd.DataFrame,
    min_market_cap: float = MIN_MARKET_CAP,
    min_price: float = MIN_PRICE,
    min_turnover: float = MIN_TURNOVER,
) -> pd.DataFrame:
    """
    Mark (never delete) which rows are investable, as `in_universe`.

    Three screens, each with a measurement reason as well as a trading one:

      min_price      Source prices are rounded to whole rupees. At ₹15 that is
                     ±3.3% quantization noise per observation — larger than the
                     weekly signal. Cheap stocks are mostly rounding artifact.
      min_turnover   A rank you cannot trade is not a signal.
      min_market_cap The microcap tail is where survivorship, reversal artifacts
                     and unadjusted corporate actions concentrate.

    Rows are FLAGGED rather than removed so the screen's effect stays auditable
    and reversible — every measurement can be re-run with the screen off.
    """
    panel = panel.copy()
    price = panel["price"].to_numpy(dtype=float)
    volume = panel.get("volume_30d", pd.Series(np.nan, index=panel.index)).to_numpy(dtype=float)
    mcap = panel.get("market_cap", pd.Series(np.nan, index=panel.index)).to_numpy(dtype=float)

    turnover = np.where(np.isfinite(price) & np.isfinite(volume), price * volume, np.nan)
    panel["turnover_30d"] = turnover
    panel["in_universe"] = (
        (price >= min_price) & (turnover >= min_turnover) & (mcap >= min_market_cap)
    )
    logger.info(
        "Universe screen: %d/%d rows investable (%.1f%%)",
        int(panel["in_universe"].sum()), len(panel),
        panel["in_universe"].mean() * 100.0,
    )
    return panel


def build_panel(
    folder: str,
    horizons_weeks: Tuple[int, ...] = (1, 2, 4, 8),
    screen: bool = True,
) -> Tuple[pd.DataFrame, PanelReport]:
    """Load -> forward returns -> corporate-action flags -> universe screen."""
    panel = load_snapshots(folder)
    panel, report = add_forward_returns(panel, horizons_weeks=horizons_weeks)
    if screen:
        panel = apply_universe_screen(panel)
    return panel, report
