# WAVE 3.0 — PRE-REGISTRATION

**Committed 2026-08-23, before any live forecast existed. This file is never edited —
amendments happen only at review windows, as dated addenda below the line.**

## The locked design (v3.0)

| element | value |
|---|---|
| Universe | Mid Cap · in_universe screen (price ≥ ₹50, mcap ≥ ₹500Cr, turnover ≥ ₹1Cr/30d) |
| Features | 10 scan percentiles + persist + sector_heat + sector_breadth (ledger #51–52) |
| Targets | wave = fwd_ret_4w ≥ +15% · crash = ≤ −15% |
| Model | logistic regression, walk-forward, 29-day embargo, min 26 training weeks |
| Table | top 30 by net edge (P(wave) − P(crash)), max 3/sector, equal weight |
| Exit (if traded) | 8-week max hold · −20% trailing stop on DAILY closes |
| Costs assumed | 57.6 bps round trip |
| Status | **EXPERIMENTAL** (failed first calibration by up to +16pp — ledger #53) |
| Review windows | every 26 logged weeks; first ≈ **2027-02-21** |

## Predictions of record (judge the log against THESE, not against hope)

1. Calibration will remain regime-biased until the training window spans both a bull
   and a corrective phase; gaps should shrink as the archive grows past ~75 weeks.
2. Top-decile P(wave) lift: **1.3–2.0×** base, not more.
3. Traded mechanically after costs: **≈ +2%/yr** vs equal-weight Mid Cap universe.
   A logged result ≥ +15%/yr means LEAKAGE until proven otherwise, not genius.
4. The same top-edge names will carry elevated P(crash) — waves break both ways.
5. sector_heat remains the largest non-range_pos contributor (Law-6 flag #52 open).
6. Statistical proof will NOT arrive (needs ~64 yrs at t=2). The 6-month verdict is
   about calibration honesty and process discipline, not proof of alpha.

## Kill criteria (pre-agreed, no renegotiation mid-flight)

- Calibration off by >10pp in ≥2 deciles after 26 LOGGED weeks → stays EXPERIMENTAL,
  banner on the table.
- Top-30 net-edge basket trails the universe by >5% over any 26 logged weeks →
  paused, autopsy in the ledger, review window advanced.
- Any leakage found → version retired permanently; the log is annotated, never wiped.

## The ritual

Sunday: `python -m alpha.weekly` → read → log freezes itself. Nothing else. Tuesday
doubts go in a notebook, not in the code. Signed into git so the jury can't be bribed.

---

## ADDENDUM — v3.1, dated 2026-08-23

**Amended before any v3.1 forecast was frozen.** v3.0 rows already in
`logs/waves_log.csv` are untouched and remain gradeable; `model_version` separates
the two, so February judges each on its own terms. The experiment forks, it does
not restart.

### What changed and on what evidence

| | v3.0 | v3.1 | evidence |
|---|---|---|---|
| Ranker | `net_edge` (13-feature logistic) | **`range_pos`** | ledger #55: 1.07× vs **1.36×** |
| Odds | fitted P(wave) | **counted decile rate** | #55 + the v3.0 calibration failure (+16pp) |
| Universe | Mid Cap (~298/wk) | **Mid + Small (~697/wk)** | ledger #57 |
| Fitted parameters | ~14 | **0** | — |

### Revised predictions of record

1. Top-decile lift **1.15–1.35×** base out of sample. (In-archive it is 1.24×;
   expect decay, not growth.)
2. The decile curve stays **U-shaped**: both extremes above the trough, trough in
   deciles 4–6. A clean ramp would be the surprise, not the goal.
3. Traded after costs: **≈ +2%/yr** over the equal-weight universe.
   A logged result ≥ +15%/yr means **leakage until proven otherwise**.
4. Large+Mega remain the weakest segment; if a future window reverses this, it is
   a review-window question, not a mid-flight change.
5. Statistical proof will NOT arrive. February judges **process honesty and log
   integrity**, not alpha.

### Revised kill criteria

- Top-decile lift < **1.10×** over 26 logged weeks → `range_pos` demoted, system
  reverts to descriptive-only with no ranking claim.
  *(Changed from "non-monotone" — ledger #58 shows the true shape is a U, and the
  old criterion would have killed the factor for behaving as theory predicts.)*
- Top-30 trails the universe by >5% over any 26 logged weeks → paused, autopsy.
- Any leakage → version retired permanently, log annotated, never reused.

**v3.1 was declared the last change before 2027-02-21.** One addendum follows; it is
recorded here rather than made quietly, because a pre-registration that gets edited
without a trace is worth nothing.

---

## Addendum 1 — 2026-08-23 · v3.1 -> v3.2 · stated odds counted on the traded universe

**What was wrong.** The odds were counted across every category while only Mid+Small
were ever bought. Decile 10 was stated at **11.96%** (n=4,501, all categories) when the
population actually purchased waved at **15.55%** (n=3,331, Mid+Small). The stated
number described a population the system never touches.

**Why it could not wait for the window.** `track_record` grades the STATED rate against
the REALIZED hit rate of the picks. Stated 3.6pp too low, against an actual drawn from
a better population, produces a spurious positive gap — the system would have looked
better calibrated than it is, for 26 weeks, and the February verdict would have been
built on it. The error ran in the direction that flatters us, which is the one direction
this project treats as unacceptable.

**The test that separates a correction from a tune: does it change a pick?** It does not.
Verified on the live archive — the 30 selected tickers and their rank order are byte
identical before and after. The ranking never consulted the odds; `range_pos` alone
orders the table. Only the reported statistic moved. A change that alters selection
would be a tune and would have waited for the window.

**What changed.** `score_panel` restricts the counting basis to `UNIVERSE_CATEGORIES`
before `attach_counted_odds`, and `base_up`/`base_dn` move to the same basis so `lift`
divides like by like (top-decile lift reads 1.405x on the consistent basis, against
1.236x when a Mid+Small rate was divided by an all-category base).

**Log consequence.** `MODEL_VERSION` -> **3.2**. `LOG_COLUMNS` is unchanged, so the log
file is NOT archived; the one existing v3.1 row (snapshot 2026-08-16) stays exactly as
frozen. February must group by `model_version` and never average a v3.1 stated rate
with a v3.2 one — they describe different populations.

**Pinned by** `test_odds_are_counted_on_the_traded_universe_not_everything` and
`test_score_panel_counts_on_universe_categories`.

**Nothing else moves before 2027-02-21.** This addendum is a measurement correction, not
a licence. Any change that touches a pick waits for the window.
