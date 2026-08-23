# WAVE 3.1 — MASTER PLAN

**The Counting Engine. Written 2026-08-23, before construction.
This document outranks every enthusiasm that comes after it.**

---

## 0. What changed from v3.0, and why

v3.0 forecast. v3.1 counts. The difference is the whole project.

| | v3.0 | v3.1 |
|---|---|---|
| Ranking | `net_edge` from a 13-feature logistic | **`range_pos`**, one measured column |
| Odds | model-predicted P(wave) | **historical decile hit rate, counted** |
| Universe | Mid Cap (~298/wk) | **Mid + Small (~697/wk)** |
| Fitted parameters | ~14 | **0** |

**The measurement that forced it** (ledger #55, same 17 OOS weeks, same stocks):

```
ranker                          top-decile hit   lift   top-30 hit   top-30 fwd 4w
range_pos alone                       18.61%     1.36×      17.84%        +5.54%
model P(wave)                         16.77%     1.22×      16.08%        +3.90%
model net_edge (the v3.0 product)     14.68%     1.07×      12.75%        +3.17%
universe average                                                          +3.02%
```

The model was not neutral decoration — it was **subtracting** performance. Mechanism,
not fluke: `net_edge` subtracts the crash model (the weakest component, over-predicting
by 9.6pp), and the logistic spread weight across 12 features already measured near zero,
diluting the one that works.

**Wave Detection buried `range_pos` under six component scores. v3.0 buried it under
thirteen.** Different machinery, same error. The measurement caught it in a day.

**And the universe (ledger #57):** v3.0's Mid-Cap-only restriction was over-tight —
imposed on a t=1.48 finding. Widening to Mid+Small more than doubles breadth. But "all
stocks" is wrong too: unrestricted, Large+Mega take **13 of 30 slots (43%)** and drag
the result from +15.18% to +6.42%/yr. Large caps rank high on `range_pos` because they
are *less volatile* — a steady grind puts them at the 95th percentile of a narrow range,
which is a different event from a mid cap at the 95th percentile of a wide one.

---

## 1. Mission

Every week, for ~697 investable Indian stocks, publish a ranked list where **every number
on screen is a fact**, and freeze it before the outcome exists.

Two kinds of "probability" wear the same word. Only one is allowed here:

- ❌ **Stated/fitted** — *"this stock has a 19% chance."* A claim about the future.
  Requires a model, calibration, and 26 weeks to verify. **v3.0 tried this and failed
  by 16pp.**
- ✅ **Counted** — *"of 16,769 past stock-weeks in this decile, 18.6% waved."*
  A count of your own data. Cannot be miscalibrated because nothing was fitted.

**Success (written now, judged 2027-02-21):**
- The frozen log grades cleanly: forecast-vs-outcome, no ambiguity about what was claimed.
- Top-decile lift ≥ 1.2× the base wave rate, out of sample.
- Traded mechanically: ~**+2%/yr** over the equal-weight universe after 57.6bps.
  **Not 15%. Two.**

**Non-goals:** predicting individual stocks, market timing, beating a momentum index fund
at scale, statistical proof (impossible at IR≈0.25 within a lifetime — §8).

---

## 2. The Laws (each one paid for in blood)

1. **Counted, never fitted.** A number reaches the screen only if outcomes produced it.
   (42 patterns carried weights −15…+28; measured edge of all 42: zero.)
2. **Percentiles, never absolute thresholds.** `master_score` drifted 40.7→52.1 in a year
   and silently broke every fixed cutoff downstream.
3. **Forward returns join on calendar dates.** Delistings = −100%, counted. Corporate
   actions detected via 52w-level rescaling. Pinned by tests.
4. **Costs always: 57.6 bps round trip.** A frictionless number is not a result.
5. **Stops evaluated on DAILY prices only.** Weekly closes overstated stop value by 22pp/yr.
6. **State the prediction before running.** A result far better than predicted is treated
   as a **bug** until proven otherwise.
7. **The test ledger.** ~57 configurations burned. E[max|t|] under noise ≈ √(2·ln N).
   Every future test appends to `TEST_LEDGER.md`. Untracked testing is the crime.
8. **Volatility ≠ direction.** Future losers out-scored future gainers on ret_7d/ret_30d.
   Raw momentum flags movers, not winners.
9. **The log cannot be bribed.** Append-only, timestamped, never edited. A snapshot
   already logged is refused, not duplicated.
10. **Locked means locked.** v3.1 is the LAST change before the February review.
    Parameter changes only at scheduled windows, only with out-of-sample evidence.
11. **Simplify on evidence; never add on hope.** Removing a layer that measured negative
    is legitimate. Adding a factor because it might help is how 35,000 lines happened.
12. **A test must never reach production data.** `append_log` resolves its path at call
    time — a default-bound path let a test corrupt the frozen log until git restored it.

---

## 3. Architecture

```
DATA        core/panel.py      honest forward returns · delistings=-100% · corp-action
                               quarantine · universe screen FLAGGED never deleted
              │
STAGE 1     core/scan.py       10 raw measurements -> within-week percentiles
              │
STAGE 2     core/track.py      time axis (persist) + sector axis (heat, breadth)
              │
STAGE 3     core/counted.py    ★ NEW: historical decile hit rates — the odds, COUNTED
              │
STAGE 4     core/decide.py     rank by range_pos · top 30 · 3/sector · freeze to log
              │
LAB         core/odds.py       the fitted model, DEMOTED. Available, labelled
                               "tested, did not earn its place — ledger #55"
GOVERNANCE  PLAN.md · PREREGISTRATION.md · TEST_LEDGER.md · git · GitHub Action
```

---

## 4. Stage specs

### Stage 1 — SCAN
Ten features, each converted to a **within-week percentile** across the investable
universe. `range_pos` is the ranker; the rest are context columns and Lab inputs.

| feature | formula | status |
|---|---|---|
| **`range_pos`** | (price−low_52w)/(high_52w−low_52w) | **THE RANKER.** IC≈0.076@8w, confirmed by a 37-yr 9-universe study |
| `from_high` | price/high_52w − 1 | context (same family) |
| `ret_7d/30d/6m` | as sourced | context (Law 8: movers, not winners) |
| `rvol`, `vol_trend` | volume ratios, **correct units** | context (fixes the 87.55%-false "declining" bug) |
| `px_sma50`, `px_sma200` | price/SMA | context |
| `log_mcap` | log(market_cap) | context |

Banned: pattern flags, market states, composite scores.

### Stage 2 — TRACK
`persist` (consecutive weeks in the top tercile), `sector_heat`, `sector_breadth`.
Displayed and filterable — **not** blended into the rank. Both earned their measurement
(ledger #51–52); neither beat `range_pos` alone as a ranker.

### Stage 3 — COUNTED ★
For each `range_pos` decile, over every labelled row in the archive: how often did a
wave (+15% / 4w) follow? Each stock displays its decile's historical rate, with **n**
and the base rate beside it.

```
SWANDEF   94th pct   ->   this decile waved 18.6% of the time   (n=16,769, base 13.7%)
```

- Bins are **deciles**, not finer: 10 bins over ~45k rows ≈ 4,500/cell. Finer bins are
  noise; conditioning on 3 features would give ~45/cell.
- **The measured shape is a U, not a ramp** (ledger #58):

  ```
  decile  1 → 10.09%  (1.04×)   near 52-week LOWS, elevated
  decile  5 →  7.49%  (0.77×)   the dead zone
  decile 10 → 11.98%  (1.24×)   near 52-week HIGHS, best
  ```

  Extremes carry the signal; the middle is empty. Wave Detection's position_score
  docstring asserted this exact philosophy — *"Extremes matter, middle doesn't"* —
  and never counted it, while implementing it on the wrong column.

  **This is also the third mechanism for the model's failure:** a logistic regression
  fits a monotone relationship, and the truth here is U-shaped. It structurally could
  not represent the pattern. Counting can, because counting assumes nothing.

  Long-only still ranks descending (decile 10 is the best cell), but the U is what
  the display shows and what the kill criterion watches.
- **Known limit, stated honestly:** the rate is computed on the same archive used to
  choose `range_pos`. It is a fact about the past, not an escape from the sample. Only
  the February log escapes it.

### Stage 4 — DECIDE
Rank by `range_pos` → top 30 → max 3/sector → freeze to `logs/waves_log.csv`.
Zero new modelling.

---

## 5. Locked parameters (v3.1)

| parameter | value | why |
|---|---|---|
| Universe | **Mid + Small Cap**, ~697/wk | Large+Mega take 43% of slots and measured weakest 3× |
| Screen | price ≥ ₹50 · mcap ≥ ₹500Cr · turnover ≥ ₹1Cr | tradeability: 89–94% of Mid winners investable vs 50–63% of Small |
| Ranker | **`range_pos`** percentile | ledger #55 |
| Wave / Crash | +15% / −15% over 4 weeks | ~14% base rate: rare enough to matter, common enough to count |
| Portfolio | top 30, max 3/sector, equal weight | the cap is **the seatbelt** — never tuned |
| Hold | 8 weeks max | survives costs at 6.5 turns/yr |
| Stop | −20% trailing, **daily** closes | cheapest insurance in the hostile (trend) regime |
| Costs | 57.6 bps round trip | ICRA/STT reality |
| Review | every 26 logged weeks; first **2027-02-21** | Law 10 |

---

## 6. The weekly ritual (0 minutes)

The GitHub Action runs Sunday 17:30 UTC: fetch Drive → rank → commit the log.
**You do nothing.** Open the app when you want to look. The experiment proceeds either way.

---

## 7. Predictions on the record

1. Top-decile lift **1.2–1.5×** base, out of sample. Not more.
2. Traded after costs: **≈ +2%/yr** vs the equal-weight universe.
   A logged result ≥ +15%/yr means **leakage until proven otherwise**, not genius.
3. The same top-ranked names will show elevated crash rates — waves break both ways.
4. `sector_heat` remains the largest non-`range_pos` signal (Law-6 flag #52 open).
5. Statistical proof will NOT arrive (~64 yrs at IR 0.25). February judges **process
   honesty and log integrity**, not proof of alpha.

## 8. Kill criteria (pre-agreed, no renegotiation mid-flight)

- Top-30 trails the universe by >5% over any 26 logged weeks → paused, autopsy in the
  ledger, review advanced.
- **Top-decile lift falls below 1.10× across 26 logged weeks** → `range_pos` demoted,
  system reverts to descriptive-only with no ranking claim.
  (NOT monotonicity — the measured shape is a U, see §4 Stage 3. Requiring a ramp
  would kill a factor for behaving exactly as theory predicts.)
- Any leakage found → version retired permanently, log annotated, never reused.

---

*The old system's epitaph, and this system's founding rule:*
**"Every idea was plausible. None was ever asked to prove itself." — here, everything is counted.**
