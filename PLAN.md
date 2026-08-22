# WAVE 3.0 — MASTER PLAN

**The Probability Engine. Written 2026-08-23, before construction. This document outranks
every enthusiasm that comes after it.**

---

## 1. Mission

Every week, for ~2,100 Indian stocks, answer one question with a number that can be
caught lying:

> **"What is the probability a wave (+15% in 4 weeks) forms in this stock — and the
> probability of the opposite?"**

Deliver it as a 30-name Mid Cap table, 2 minutes a week, forecasts frozen to a log
*before* outcomes exist.

**Definition of success (written now, judged in 6 months):**
- Calibration: when the model says X%, reality lands within ±5pp of X — measured on
  frozen forecasts only.
- Top-decile lift: ≥ 1.5× the base wave rate, out of sample.
- Traded expectation IF followed mechanically: ~**+2%/yr** over the equal-weight Mid Cap
  universe after 57.6bps costs. **Not 19%. Not 56%. Two.**

**Non-goals:** predicting the market's direction, beating a momentum index fund at scale,
statistical proof (impossible at IR≈0.25 inside a human lifetime — see §8), replacing
the user's judgment.

---

## 2. The Laws (each one paid for in the 2026-08-22 audit)

1. **Earned, never stated.** No number reaches a screen unless outcomes produced it.
   (42 patterns carried weights −15…+28; measured edge of all 42: zero.)
2. **Percentiles, never absolute thresholds.** `master_score` drifted 40.7→52.1 in a
   year and silently broke every fixed cutoff.
3. **Forward returns join on calendar dates.** Delistings = −100%, counted. Corporate
   actions detected via 52w-level rescaling, quarantined. (Already enforced in `panel.py`,
   pinned by 18 tests.)
4. **Costs always: 57.6 bps round trip.** A frictionless number is not a result.
5. **Stops are evaluated on DAILY prices only.** Weekly closes overstated stop value by
   22pp/yr.
6. **State the prediction before running.** Every test in §8 has its expected result
   written here first. A result wildly better than predicted is treated as a **bug**
   until proven otherwise.
7. **The test ledger.** ~50 configurations were burned in the audit; E[max|t|] under
   noise at 50 tests ≈ 2.2–2.7. Every future test appends to `alpha/TEST_LEDGER.md`.
   The bar rises with the count; untracked testing is the crime, not failed tests.
8. **Volatility ≠ direction.** Every raw momentum signal flags movers, not winners
   (future losers out-scored future gainers on ret_7d/ret_30d). Direction lives only
   in the calibrated model, never in a raw signal.
9. **The log cannot be bribed.** Weekly forecasts are appended, timestamped, and never
   edited. The 6-month verdict reads the log, not memory.
10. **Locked means locked.** Parameter changes only at scheduled 6-month review windows,
    only with out-of-sample evidence from the log.

---

## 3. Architecture

```
DATA LAYER          alpha/panel.py (BUILT, 18 tests green)
  weekly archive ──► honest panel: fwd returns 1/4/8w, delistings, corp-actions,
  daily archive  ──► daily price matrix (stops & execution truth)
        │
STAGE 1 SCAN        alpha/scan.py           (~150 lines)   replaces 21,132
  10 clean features, cross-sectional percentiles, zero opinions
        │
STAGE 2 TRACK       alpha/track.py          (~150 lines)   replaces 13,784
  the time axis: persistence, trajectory, wave age
        │
STAGE 3 ODDS        alpha/odds.py           (~250 lines)   the missing half
  walk-forward P(wave), P(crash); calibration is the judge
        │
STAGE 4 DECIDE      alpha/weekly.py         (~150 lines)   the product
  the Sunday table + frozen log + portfolio/exit rules
        │
GOVERNANCE          PLAN.md (this) · PREREGISTRATION.md · TEST_LEDGER.md · git
```

---

## 4. Stage specs

### Stage 1 — SCAN (features)
Computed weekly, each converted to a **within-week percentile** before use:

| # | feature | formula | why it earned a seat |
|---|---------|---------|----------------------|
| 1 | `range_pos` | (price−low_52w)/(high_52w−low_52w) | the survivor: IC≈0.076@8w, confirmed by 37-yr 9-universe study; volatility-normalized by construction |
| 2 | `from_high` | price/high_52w − 1 | the same family's second face; kept as model input, not standalone |
| 3 | `ret_7d`, 4: `ret_30d`, 5: `ret_6m` | as sourced | direction context for the model (raw ICs ~0; the model may still use them conditionally) |
| 6 | `rvol` | vol_1d/vol_90d | wave-energy detector (both directions) |
| 7 | `vol_trend` | vol_30d/vol_90d | **correct units** — deviation vs baseline, fixing the 87.55%-false "declining" bug |
| 8 | `px_sma50`, 9: `px_sma200` | price/SMA | trend context |
| 10 | `log_mcap` | log(market_cap) | size effect carrier |

Explicitly banned: pattern flags, market states, composite scores, anything with an
opinion baked in.

### Stage 2 — TRACK (time + sector axes) — *two* pre-registered tests

**Time axis (test T1):**
- `persist` = consecutive weeks in top tercile of `range_pos`
- `trend_4w` = range_pos percentile now − 4 weeks ago
- `wave_age` = weeks since range_pos percentile first crossed 80

**Sector axis (test T2 — SECTOR ROTATION, the one idea the audit argued FOR):**
- `sector_heat` = sector's average range_pos percentile this week
- `sector_breadth` = share of the sector's members in the top tercile (breadth beats
  average when one outlier drags a dead sector up)
- `sector_heat_d4` = sector_heat now − 4 weeks ago (is the rotation arriving or leaving)

Evidence on record: portfolio alpha rose monotonically as the sector cap loosened
(2/sector +1.50% → uncapped +11.70%/yr) — the sector bet carries real return. Industry
momentum is independently documented (Moskowitz–Grinblatt 1999). The old system's
`detect_sector_rotation`/LDI modules asserted this without ever testing it; here it
enters as features feeding ODDS, where the calibration table judges it.

**Predictions (Law 6):**
- T1 persistence: modest — combined IC 0.08→~0.09. Transformative ⇒ hunt the bug.
- T2 sector heat: the strongest candidate addition — but substantially overlapping
  stock-level range_pos (hot sectors ARE where high-range_pos stocks live). Expected
  incremental IC +0.01–0.02. Its real job may be risk: telling you when the
  concentration the cap protects against is building.
- The 3/sector cap STAYS regardless of T2's result. Rotation is return; the cap is
  the seatbelt against the −70% industry-crash tail. We ride rotation through the
  probability model, never by uncapping.

### Stage 3 — ODDS (the probability machine)
- Targets: `up` = fwd_ret_4w ≥ +15% · `dn` = fwd_ret_4w ≤ −15%
- Model: **logistic regression** on Stage-1(+2 if survives) percentiles. Deliberately
  boring — at ~50k rows and 52 weeks, anything fancier is overfitting with better PR.
  (Gradient boosting may be *ledger-tested once* at the 6-month review, never before.)
- **Walk-forward only:** forecast for week *t* uses a model fit on weeks < *t*−4
  (embargo = the label horizon, so no label leakage). Minimum 26 training weeks.
- Judged by: calibration table (deciles: stated vs actual), lift curve, and
  **P(up)−P(dn) net edge** — because Law 8 says the same stocks carry both tails.
- Retrains automatically as the archive grows. **This is the feedback loop the old
  system never had.**

### Stage 4 — DECIDE (the product)
Sunday, one command:
```
WAVE 3.0 · 2026-08-23 · MidCap univ 309 · model v3.0 (trained ≤ 2026-07-26)
ticker       P(wave)  P(crash)  edge  persist  age  verdict
KABRAEXTRU     31%      12%     +19     5w      6w   🌊 SURF
...top 30 by edge, max 3/sector...
```
- Appended immutably to `alpha/waves_log.csv` (date, model version, full table).
- Portfolio rules (for the paper/live track): top 30 by **net edge**, max 3/sector,
  equal weight, 8-week max hold, **−20% trailing stop on daily closes** (tail
  insurance, priced at ~1.7pp/yr in trend — accepted).

---

## 5. Locked parameters (v3.0)

| parameter | value | source |
|---|---|---|
| Universe | Mid Cap, in_universe screen (₹50 floor, ₹500Cr mcap, ₹1Cr turnover) | 92% of winners investable vs 57% in SmallCap; LargeCap negative |
| Wave definition | +15% / 4 weeks | ~5% base rate: rare enough to matter, common enough to calibrate |
| Crash definition | −15% / 4 weeks | symmetry, Law 8 |
| Portfolio | top 30 by net edge, 3/sector, equal wt | audit-tested |
| Hold | 8 weeks max | best-supported horizon; 6.5 turns/yr survives costs |
| Stop | −20% trailing, daily closes | cheapest insurance in the hostile (trend) regime |
| Costs | 57.6 bps round trip | ICRA/STT reality |
| Model | logistic, walk-forward, 4-week embargo | §4 |
| Review window | every 26 weeks from first log entry | Law 10 |

---

## 6. The weekly ritual (2 minutes)

1. Sunday: backup script drops the new CSV (already automated).
2. Run `python -m alpha.weekly`.
3. Read the table. Decide whatever you decide — the system logs its forecast either way.
4. Nothing else. No tweaking. Tuesday doubts go in a notebook, not in the code.

---

## 7. Build order (one session)

1. `alpha/scan.py` + tests — features, percentiles, correct units
2. `alpha/track.py` + tests — persistence trio + its ONE ledgered test
3. `alpha/odds.py` + tests — walk-forward fit, calibration table, no-leakage test pinned
4. `alpha/weekly.py` — table, frozen log, first real run
5. `PREREGISTRATION.md` + `TEST_LEDGER.md` (seeded with the audit's ~50 burned tests)
6. Commit everything; `alpha/` becomes real

---

## 8. Predictions on the record (so results can be judged, not narrated)

- Top decile P(wave): actual hit rate ~2× base (≈10% vs ≈5%), NOT more.
- Calibration: roughly monotone, ±5pp per decile after 26 training weeks.
- Persistence (T1): +0.01 IC or less.
- Sector heat (T2): +0.01–0.02 IC incremental; best single addition, mostly overlapping
  range_pos. Uncapped sector-riding stays banned whatever it shows (seatbelt rule).
- The same top-decile stocks will show elevated P(crash) — waves break both ways.
- Traded, after costs: **~+2%/yr** vs universe. If the log shows +15%/yr, first
  suspect: leakage. Statistical proof will NOT arrive (needs ~64 yrs at t=2); the
  6-month verdict is about *calibration honesty*, not proof of alpha.

## 9. Kill criteria (also on the record)

- Calibration off by >10pp in 2+ deciles after 26 logged weeks → model demoted to
  "experimental", table marked accordingly.
- Net-edge top 30 underperforms universe by >5% over any 26 logged weeks → strategy
  paused, autopsy in TEST_LEDGER, review window advanced.
- Any evidence of leakage → version retired permanently, log annotated, never reused.

---

*The old system's epitaph, and this system's founding rule:*
**"Every idea was plausible. None was ever asked to prove itself." — here, everything asks.**
