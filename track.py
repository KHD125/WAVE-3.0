"""
alpha.track — Stage 2 of WAVE 3.0 (see alpha/PLAN.md §4).

Two axes the cross-section cannot see:

TIME (test T1)      persist   consecutive weeks in the top tercile of p_range_pos
                    trend_4w  p_range_pos now − ~4 weeks ago (calendar-nearest, Law 3)
                    wave_age  consecutive weeks with p_range_pos ≥ 0.80

SECTOR (test T2)    sector_heat     sector's mean p_range_pos this week
                    sector_breadth  share of the sector in the top tercile
                    sector_heat_d4  heat now − ~4 weeks ago

T1/T2 are the ONLY two pre-registered tests (PLAN §8 predictions: T1 ≈ +0.01 IC or
less; T2 the best addition at +0.01–0.02, mostly overlapping range_pos). Run them
once via `python -m alpha.track`, record the result in TEST_LEDGER.md, lock in or out.

The 3/sector portfolio cap stays regardless of T2 (the seatbelt rule): rotation is
ridden through the probability model, never by concentrating.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TOP_TERCILE = 2.0 / 3.0
WAVE_ZONE = 0.80
LOOKBACK_DAYS = 28          # "4 weeks ago" on the calendar
LOOKBACK_TOL = 4            # nearest snapshot within ± this many days, else NaN

TRACK_FEATURES = ("persist", "trend_4w", "wave_age",
                  "sector_heat", "sector_breadth", "sector_heat_d4")


def _run_length(flag: pd.Series, by: pd.Series) -> pd.Series:
    """Consecutive-True run length within each `by` group (0 where False).

    Vectorized: a new run id starts at every False; cumcount inside (group, run)
    counts the streak. No row loops (CLAUDE.md §5 vectorization mandate).
    """
    flag = flag.fillna(False).astype(bool)
    run_id = (~flag).groupby(by).cumsum()
    # cumsum of the flag ITSELF within (group, run) — a False must not occupy a
    # slot in the count (cumcount did, inflating every post-gap streak by one;
    # caught by test_run_length_counts_consecutive_true_within_ticker).
    streak = flag.astype(int).groupby([by, run_id]).cumsum()
    return streak.where(flag, 0).astype(int)


def _past_date_map(dates: pd.Index, days: int, tol: int) -> pd.Series:
    """date -> the snapshot nearest to (date − days), within ±tol days, else NaT.

    Calendar-nearest, never an index shift: the archive holds 1-, 6- and 8-day gaps
    (Law 3 — the bug class that mislabelled every horizon after 2026-04-19)."""
    arr = np.asarray(dates, dtype="datetime64[D]")
    wanted = arr - np.timedelta64(days, "D")
    right = np.clip(np.searchsorted(arr, wanted), 0, len(arr) - 1)
    left = np.clip(right - 1, 0, len(arr) - 1)
    dl = np.abs((arr[left] - wanted).astype(int))
    dr = np.abs((arr[right] - wanted).astype(int))
    pick = np.where(dl <= dr, left, right)
    best = np.where(dl <= dr, dl, dr)
    ok = (best <= tol) & (arr[pick] < arr)
    chosen = arr[pick].astype("datetime64[ns]")
    return pd.Series(np.where(ok, chosen, np.datetime64("NaT")), index=dates)


def compute_track(panel: pd.DataFrame) -> pd.DataFrame:
    """Attach the six TRACK columns. Requires scan.compute_features to have run."""
    if "p_range_pos" not in panel.columns:
        raise KeyError("run alpha.scan.compute_features first (needs p_range_pos)")
    panel = panel.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
    p = panel["p_range_pos"]

    # ── time axis ──
    panel["persist"] = _run_length(p >= TOP_TERCILE, panel["ticker"])
    panel["wave_age"] = _run_length(p >= WAVE_ZONE, panel["ticker"])

    dates = pd.Index(sorted(panel["date"].unique()))
    past = _past_date_map(dates, LOOKBACK_DAYS, LOOKBACK_TOL)
    prior = panel[["ticker", "date", "p_range_pos"]].rename(
        columns={"date": "_past", "p_range_pos": "_p_past"})
    panel["_past"] = panel["date"].map(past)
    panel = panel.merge(prior, on=["ticker", "_past"], how="left")
    panel["trend_4w"] = panel["p_range_pos"] - panel["_p_past"]

    # ── sector axis ── (investable rows only define the sector's temperature)
    inv = panel["in_universe"].fillna(False).astype(bool)
    sub = panel.loc[inv, ["date", "sector", "p_range_pos"]]
    heat = sub.groupby(["date", "sector"])["p_range_pos"].mean().rename("sector_heat")
    breadth = (sub.assign(t=sub["p_range_pos"] >= TOP_TERCILE)
                  .groupby(["date", "sector"])["t"].mean().rename("sector_breadth"))
    sect = pd.concat([heat, breadth], axis=1).reset_index()
    sect["_past"] = sect["date"].map(past)
    prior_heat = sect[["date", "sector", "sector_heat"]].rename(
        columns={"date": "_past", "sector_heat": "_heat_past"})
    sect = sect.merge(prior_heat, on=["sector", "_past"], how="left")
    sect["sector_heat_d4"] = sect["sector_heat"] - sect["_heat_past"]
    panel = panel.merge(sect[["date", "sector", "sector_heat", "sector_breadth",
                              "sector_heat_d4"]], on=["date", "sector"], how="left")
    return panel.drop(columns=["_past", "_p_past"])


def run_preregistered_tests(panel: pd.DataFrame) -> pd.DataFrame:
    """T1 + T2, exactly once. Per-week Spearman IC vs forward returns, plus overlap
    with p_range_pos. Output belongs in TEST_LEDGER.md verbatim — every row, no picks."""
    from scipy.stats import spearmanr

    d = panel[panel["in_universe"].fillna(False).astype(bool)
              & ~panel["is_corporate_action"].fillna(False).astype(bool)]
    rows = []
    for f in TRACK_FEATURES:
        rec = {"feature": f}
        for k in (4, 8):
            fwd = f"fwd_ret_{k}w"
            ics = []
            for _, g in d.groupby("date"):
                ok = g[f].notna() & g[fwd].notna()
                if ok.sum() > 150 and g.loc[ok, f].nunique() > 5:
                    r = spearmanr(g.loc[ok, f], g.loc[ok, fwd]).correlation
                    if np.isfinite(r):
                        ics.append(r)
            a = np.asarray(ics)
            rec[f"ic_{k}w"] = a.mean() if len(a) else np.nan
            rec[f"t_{k}w"] = (a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))
                              if len(a) > 2 else np.nan)
        ok = d[f].notna() & d["p_range_pos"].notna()
        rec["corr_vs_range_pos"] = spearmanr(d.loc[ok, f], d.loc[ok, "p_range_pos"]).correlation
        rec["n_weeks"] = len(ics)
        rows.append(rec)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    from alpha.scan import compute_features

    panel = pd.read_parquet("alpha/_panel_long.parquet")
    panel = compute_track(compute_features(panel))
    res = run_preregistered_tests(panel)
    print("PRE-REGISTERED TESTS T1 (time) + T2 (sector) — record verbatim in TEST_LEDGER.md")
    print("PLAN §8 predictions: T1 ≈ +0.01 IC or less; T2 +0.01–0.02, overlapping range_pos")
    print()
    print(res.to_string(index=False, float_format=lambda v: f"{v:+.4f}"))
