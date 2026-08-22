"""
alpha.backtest — the honest backtest.

Answers one question: after costs, does ranking on a factor beat holding the
universe? Everything here exists to stop that question being answered too
generously.

DESIGN CHOICES THAT MATTER
--------------------------
Overlapping cohorts.  An 8-week hold over 52 snapshots gives only 6 sequential
    rebalances — far too few to conclude anything. So we start a NEW portfolio
    every week and hold each for the full horizon (Jegadeesh-Titman). That gives
    ~44 cohorts instead of 6 from the same data. The cohorts overlap, so their
    returns are NOT independent: the t-stat is haircut by sqrt(horizon) and BOTH
    numbers are reported. Never quote the raw one.

Costs are charged, always.  Each cohort is a complete buy-and-hold, so it pays
    one round trip. A "gross" number is not a result; it is a hypothesis.

Delistings are already losses.  alpha.panel encodes a vanished ticker as -100%,
    so a delisted holding drags the cohort down exactly as it would have in the
    account. Nothing here filters them back out.

The benchmark is the SAME universe, equal-weighted.  Beating a cap-weighted
    index by holding small caps is not skill. The only honest comparison is
    against the pool the picks were drawn from.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

WEEKS_PER_YEAR = 52.0


@dataclass
class BacktestResult:
    """One backtest. `render()` is the only honest way to read it."""

    factor: str
    horizon_weeks: int
    top_n: int
    max_per_sector: int
    cost_bps: float

    n_cohorts: int = 0
    mean_gross_pct: float = 0.0
    mean_net_pct: float = 0.0
    mean_bench_pct: float = 0.0
    mean_alpha_pct: float = 0.0
    t_alpha_raw: float = 0.0
    t_alpha_adjusted: float = 0.0
    hit_rate_pct: float = 0.0
    worst_cohort_pct: float = 0.0
    best_cohort_pct: float = 0.0
    ann_alpha_pct: float = 0.0
    mean_holdings: float = 0.0
    cohort_alphas: List[float] = field(default_factory=list)

    def render(self) -> str:
        periods = WEEKS_PER_YEAR / self.horizon_weeks
        verdict = (
            "TRADEABLE"
            if self.t_alpha_adjusted >= 2.9 and self.mean_alpha_pct > 0
            else "promising, NOT proven"
            if self.t_alpha_adjusted >= 2.0 and self.mean_alpha_pct > 0
            else "no evidence of edge"
        )
        return "\n".join([
            "── backtest ───────────────────────────────────────────────",
            f"  factor           {self.factor}   top {self.top_n}, max {self.max_per_sector}/sector",
            f"  hold             {self.horizon_weeks}w  ({periods:.1f} rebalances/yr)",
            f"  cost             {self.cost_bps:.0f} bps round trip",
            f"  cohorts          {self.n_cohorts}  (overlapping)",
            f"  avg holdings     {self.mean_holdings:.0f}",
            "  ",
            f"  gross / cohort   {self.mean_gross_pct:+7.3f}%",
            f"  net   / cohort   {self.mean_net_pct:+7.3f}%   (after cost)",
            f"  benchmark        {self.mean_bench_pct:+7.3f}%   (same universe, equal weight)",
            f"  ALPHA            {self.mean_alpha_pct:+7.3f}%   per {self.horizon_weeks}w",
            f"  annualised       {self.ann_alpha_pct:+7.2f}%",
            "  ",
            f"  t (raw)          {self.t_alpha_raw:+6.2f}   <- overlapping, INFLATED",
            f"  t (adjusted)     {self.t_alpha_adjusted:+6.2f}   <- divide by sqrt({self.horizon_weeks}); use this",
            f"  hit rate         {self.hit_rate_pct:5.1f}%  of cohorts beat the universe",
            f"  worst / best     {self.worst_cohort_pct:+.2f}% / {self.best_cohort_pct:+.2f}%",
            "  ",
            f"  VERDICT          {verdict}",
            "───────────────────────────────────────────────────────────",
        ])


def select_holdings(
    week: pd.DataFrame, factor: str, top_n: int, max_per_sector: int
) -> pd.DataFrame:
    """
    Top `top_n` by `factor`, admitting at most `max_per_sector` from any sector.

    The sector cap is the only risk control in the model and it is not
    negotiable: an unconstrained top-40 on a momentum-like factor reliably
    becomes a single-sector bet, and then one sector unwind is the whole result.
    """
    ranked = week[week[factor].notna()].sort_values(factor, ascending=False, kind="mergesort")
    if max_per_sector and "sector" in ranked.columns:
        within_sector = ranked.groupby("sector", sort=False).cumcount()
        ranked = ranked[within_sector < max_per_sector]
    return ranked.head(top_n)


def run_backtest(
    panel: pd.DataFrame,
    factor: str,
    horizon_weeks: int = 8,
    top_n: int = 40,
    max_per_sector: int = 3,
    cost_bps: float = 25.0,
    min_universe: int = 150,
    min_holdings: int = 10,
) -> BacktestResult:
    """
    Overlapping-cohort backtest of a single cross-sectional factor.

    Each snapshot date forms one cohort: buy the selected names equal-weighted,
    hold `horizon_weeks`, take the realised forward return, charge one round
    trip. Alpha is measured against the same universe, equal-weighted, over the
    identical window — so market direction cancels and only selection remains.
    """
    result = BacktestResult(
        factor=factor, horizon_weeks=horizon_weeks, top_n=top_n,
        max_per_sector=max_per_sector, cost_bps=cost_bps,
    )
    fwd_col = f"fwd_ret_{horizon_weeks}w"
    if fwd_col not in panel.columns:
        raise KeyError(f"panel has no {fwd_col}; build it with the matching horizon")

    tradeable = panel[panel.get("in_universe", True) & ~panel.get("is_corporate_action", False)]

    gross, bench, sizes = [], [], []
    for _, week in tradeable.groupby("date", sort=True):
        scored = week[week[factor].notna() & week[fwd_col].notna()]
        if len(scored) < min_universe:
            continue  # too thin to rank, or past the end of the forward window
        holdings = select_holdings(scored, factor, top_n, max_per_sector)
        if len(holdings) < min_holdings:
            continue
        gross.append(float(holdings[fwd_col].mean()))
        bench.append(float(scored[fwd_col].mean()))
        sizes.append(len(holdings))

    if not gross:
        logger.warning("No cohort had enough data to evaluate")
        return result

    gross_arr = np.asarray(gross, dtype=float)
    bench_arr = np.asarray(bench, dtype=float)
    net_arr = gross_arr - cost_bps / 100.0   # one round trip per cohort
    alpha_arr = net_arr - bench_arr

    result.n_cohorts = len(alpha_arr)
    result.mean_gross_pct = float(gross_arr.mean())
    result.mean_net_pct = float(net_arr.mean())
    result.mean_bench_pct = float(bench_arr.mean())
    result.mean_alpha_pct = float(alpha_arr.mean())
    result.hit_rate_pct = float((alpha_arr > 0).mean() * 100.0)
    result.worst_cohort_pct = float(alpha_arr.min())
    result.best_cohort_pct = float(alpha_arr.max())
    result.mean_holdings = float(np.mean(sizes))
    result.cohort_alphas = alpha_arr.tolist()

    # Guarded t-stat: a single cohort, or a degenerate series, has no t.
    std = alpha_arr.std(ddof=1) if len(alpha_arr) > 1 else np.nan
    result.t_alpha_raw = float(
        alpha_arr.mean() / (std / np.sqrt(len(alpha_arr)))
    ) if np.isfinite(std) and std > 0.0 else 0.0
    # Cohorts overlap by `horizon_weeks`, so ~1 in `horizon_weeks` is independent.
    result.t_alpha_adjusted = float(result.t_alpha_raw / np.sqrt(horizon_weeks))

    periods = WEEKS_PER_YEAR / horizon_weeks
    result.ann_alpha_pct = float(((1.0 + result.mean_alpha_pct / 100.0) ** periods - 1.0) * 100.0)
    return result


def sweep_costs(
    panel: pd.DataFrame, factor: str, cost_grid=(0.0, 15.0, 25.0, 50.0, 100.0), **kwargs
) -> pd.DataFrame:
    """
    Alpha as a function of assumed cost — the honest way to present a result.

    A single cost assumption invites the reader to trust it. The whole curve
    shows exactly where the edge dies, and lets anyone substitute their own
    execution reality.
    """
    rows = []
    for cost in cost_grid:
        r = run_backtest(panel, factor, cost_bps=cost, **kwargs)
        rows.append({
            "cost_bps": cost,
            "alpha_pct": round(r.mean_alpha_pct, 3),
            "ann_alpha_pct": round(r.ann_alpha_pct, 2),
            "t_adjusted": round(r.t_alpha_adjusted, 2),
            "hit_rate_pct": round(r.hit_rate_pct, 1),
        })
    return pd.DataFrame(rows)
