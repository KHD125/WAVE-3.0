# WAVE 3.0 — TEST LEDGER

Every hypothesis ever run against this dataset, on the record. The multiple-testing
bar rises with this file's length (PLAN Law 7): at ~50 tests, E[max|t|] under pure
noise ≈ 2.2–2.7. **An untracked test is the crime; a failed test is just data.**

| # | date | test | result | verdict |
|---|------|------|--------|---------|
| 1–50 | 2026-08-22 | The audit burn: ~50 configurations across factor ICs (9 signals × 4 horizons), universe screens (4 floors), backtest grids (hold × topN × sector-cap), stop rules (9 variants × 2 resolutions), segment splits (4), pattern sweep (42 patterns), master_score/S2/S3 replication | Best |t| anywhere = 1.45 (MidCap 8w top-10%). All 42 patterns < |t| 2.0. Weekly stops overstated by 22pp/yr vs daily. | `range_pos` sole survivor; design locked in PLAN.md; **the mine is exhausted** |
| 51 | 2026-08-23 | **T1 (pre-registered): persistence trio** — persist / trend_4w / wave_age vs fwd 4w/8w | persist IC +.066/+.080 (raw t 5.9/7.7) but corr 0.81 vs range_pos → same factor, time costume. trend_4w noise (−.019/+.015). wave_age = persist's twin (corr 0.69/…) | **persist IN** (one seat) · wave_age OUT · trend_4w OUT. Prediction (≤+0.01 incremental) ≈ met |
| 52 | 2026-08-23 | **T2 (pre-registered): sector rotation** — sector_heat / sector_breadth / sector_heat_d4 | sector_heat IC +.063/+.098 (raw t 5.5/7.8; overlap-adj ≈2.8 — strongest number of the project) at only 0.36 corr vs range_pos. breadth similar. d4 dead (+.005/+.022) | **sector_heat + sector_breadth IN** · d4 OUT. ⚠ BETTER than the +0.01–0.02 prediction — Law-6 flag recorded; leak checks passed (same-week percentiles only); mechanism = industry momentum (Moskowitz–Grinblatt 1999). Re-examine at first review window |
| 53 | 2026-08-23 | **First walk-forward calibration** — logistic, 13 features, 29-day embargo, 22 OOS weeks (2026-03-29→08-16), 21,665 rows | P(wave) miscalibrated up to **+16.3pp** (regime shift: trained mixed market, tested bull; base rate 15.7% OOS). Ranking U-shaped (bull-recovery favored beaten-down names — Law 8). P(crash) monotone but over-predicted up to −9.6pp. Top-decile lift 1.22× (predicted ~2×) | Model ships **EXPERIMENTAL** per PLAN §9. No repair attempted — the live log (waves_log.csv) is the only permitted judge. Kelly sizing stays REFUSED until calibration passes |
| 54 | 2026-08-23 | `_run_length` streak bug (post-gap streaks +1) found by contract test; T1 re-run after fix | persist +.0662→+.0656; rank order preserved; conclusions unchanged | Fix committed; ledger notes the re-run so #51 isn't silently two tests |

**Open Law-6 flags:** #52 sector_heat (better than predicted).
**Standing refusals:** Kelly/fractional-Kelly sizing (gated on calibrated p — see #53 and PRISM MOD 5 precedent) · uncapped sector concentration (seatbelt rule) · any new factor without a ledger row.
