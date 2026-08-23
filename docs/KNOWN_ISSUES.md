# WAVE 3.1 — known issues

Parked items. Checked at the start of each session.

## 1. GitHub Action cannot run — account billing lock (2026-08-23) · PARKED

```
Status Failure · Total duration 5s
The job was not started because your account is locked due to a billing issue.
```

**Not a code fault.** The job never started — GitHub refused before reading the
workflow, so there are no step logs. Workflow, config and the Drive URL are all
verified working (`python -m tools.weekly_run` succeeds locally end to end).

Note: Actions on **public** repos have unlimited free minutes, so the lock is
almost certainly an unpaid item elsewhere on the account, not a cost from this job.

**To resume:** clear the item at github.com/settings/billing, then
Actions → weekly forecast → Run workflow. Nothing in the repo needs changing.

**Consequence while parked:** the weekly forecast is NOT being frozen automatically.
Every un-frozen Sunday is a permanent hole in the February evidence — the log cannot
be backfilled honestly, because a forecast written after the outcome is not a forecast.

**Interim (manual, ~1 min):**
```
cd "S:\Stock Scan (Build)\alpha"
..\.venv\Scripts\python.exe -m tools.weekly_run
git add logs/waves_log.csv && git commit -m "log: week of <date>" && git push
```

**Alternative if billing stays blocked:** Windows Task Scheduler running the same
three commands. Equally automatic, but only fires when the PC is on — GitHub's
runner does not care, which is why it remains the preferred host.

## 2. Drive folder is 2 weeks behind the local archive (2026-08-23) · OPEN

Drive Weekly ends **2026-08-02**; the local archive has **2026-08-16**. Two backups
have not uploaded. Once the Action is live, Drive becomes the system's only data
source, so a stalled backup means the job quietly freezes stale odds every week.

**To check:** the Apps Script execution log for `runWeeklyBackup` (Sunday 21:00 IST).

## 3. Sheet-side fixes worth doing (2026-08-23) · OPEN

Cheap, and they improve every future snapshot:
- **Price number format → 2 decimals.** Prices export rounded to whole rupees; at
  ₹15 that is ±3.3% quantisation noise per observation.
- **Move `moving_avg3` / `volume_data` / `calculated` 30 min earlier.** They run at
  12:03–12:15 AM IST, so `TODAY()` has rolled over and `sma_200d` plus every volume
  average use a window one day later than `price` and the returns.
- **Delete `Stocks_Weekly_2026-04-25`** — a manual Saturday run duplicating the
  2026-04-26 snapshot (96.13% identical prices).
- **Regenerate `Stocks_Daily_2026-04-22`** — its first column header is `#REF!`, a
  live sheet error frozen into the backup.

## 4. Bumping MODEL_VERSION: archive the log, never append across schemas (2026-08-23) · RULE

A CSV append writes no header row. When v3.1 widened `LOG_COLUMNS` from 13 to 16,
the new rows landed under the old header and every later read died with
`Expected 13 fields in line 32, saw 16` — the frozen experiment record was
unreadable until git restored it.

`append_log` now refuses on a header mismatch. **When a version bump changes
`LOG_COLUMNS`:**
1. `git mv logs/waves_log.csv logs/waves_log_v<old>.csv` — the old rows stay
   gradeable and February grades the versions separately.
2. Let the next run start a fresh `waves_log.csv`.
3. Check `core/track_record.py::_STATED_CANDIDATES` covers the new schema's
   stated-probability column — v3.1 renamed it `p_up` → `hist_rate`, and the
   live-record branch only fires at 30+ graded rows, so a miss there hides until
   the app first has real evidence to show.

## 5. `tools/weekly.ps1` — VERIFIED, after it turned out not to parse (2026-08-23) · CLOSED

The Task Scheduler fallback for issue 1. When finally run, **it did not parse at
all** — as a scheduled task it would have done nothing every Sunday, silently,
which is worse than no fallback because it looks like coverage.

**Cause:** Windows PowerShell 5.1 reads a `.ps1` as ANSI unless the file carries a
UTF-8 BOM. The script contained em-dashes; under cp1252 the `0x94` byte decodes to
a right double quote, which PowerShell honours as a string delimiter. Strings
closed early, braces went unbalanced, the parse failed at a line far from the
cause. **Rule: keep `.ps1` files ASCII-only** — pinned by
`tests/test_ui_contract.py::test_powershell_fallback_is_ascii_and_parses`.

Also dropped `$ErrorActionPreference = "Stop"`: under 5.1 it converts a native
program's stderr into a terminating `NativeCommandError`, so a Python traceback
would abort the script before it could read `$LASTEXITCODE` and report the real
reason. Every failure is now checked explicitly.

**Verified end to end 2026-08-23:** downloaded 50 CSVs from Drive, hit the
freshness guard on the 21-day-old snapshot, reported it, exited 1, and committed
nothing. The one path still unexercised is the success branch (commit + push),
which needs a fresh snapshot to reach.

## 6. The first logged row is 7 days stale, and predates the guard (2026-08-23) · DISCLOSED

`waves_log.csv` row set 1 — snapshot **2026-08-16**, frozen **2026-08-23**. The
freshness guard (`MAX_SNAPSHOT_AGE_DAYS = 5`) was written immediately afterwards and
would REFUSE this row today; running `python -m core.decide` now exits 1 on it.

It stays in the log. The log is append-only precisely so that rows cannot be dropped
later for looking inconvenient, and dropping one on day one would set exactly the
wrong precedent. What a February reader needs to know:

- **No lookahead reached the model.** Every feature is computed from the 08-16 panel;
  `score_panel` never sees a later bar.
- **1 of the 4 label weeks had already elapsed** when the row was written, so a human
  could in principle have known part of the outcome. Nobody looked, but the claim is
  unfalsifiable — treat this row as weaker evidence than the ones that follow.
- The gap is **auditable from the log itself**: `logged_at_utc` minus `snapshot_date`
  is 7 days here and should be 0 for every honest row after it. Check that column
  before grading.

**Next clean freeze:** after the Sunday 21:00 IST backup lands, `python -m core.decide`
sees age 0.

## 7. Streamlit Cloud deploy failed: requirements.txt could not resolve (2026-08-23) · FIXED

`ResolutionImpossible`. One line caused it:

```
streamlit 1.54.0 depends on pandas<3 and >=1.4.0
The user requested pandas~=3.0.0
```

`streamlit<=1.55` declares `pandas<3`, so `streamlit~=1.54.0` beside `pandas~=3.0.0`
is unsatisfiable and Cloud's installer aborts **before the app is ever built**. The
`rich`/`pygments` reinstall further down that log is Cloud setting up its own
fallback exception logger — unrelated, and a red herring.

**Why nothing caught it:** the file was never resolved end to end. The dev venv had
streamlit 1.54.0 and pandas 3.0.0 installed side by side because pip only WARNS when
an upgrade breaks an existing pin — `pip check` reported it while everything ran
fine locally. The environment worked and was simultaneously impossible to reproduce.

**Fix:** `streamlit~=1.56.0`, the EARLIEST release permitting pandas 3. Deliberately
not the newest (1.62), which swaps Tornado for Uvicorn/Starlette — a large change to
absorb mid-experiment for no benefit. Verified in a clean venv built from
requirements.txt alone: resolves, and all 58 tests pass including the AppTest suite
that renders the real app.

**Pinned by** `test_requirements_are_internally_consistent` — `pip check` narrowed to
our own pins, needs no network, and reproduces this exact failure offline. It SKIPS
when the environment does not match requirements.txt, so a drifted dev venv reports
honestly rather than raising a false alarm.

**Still unverified: Python 3.14.** Cloud runs 3.14.7; this machine has only 3.13 and
3.11, so the suite has never run on 3.14. The cp314 wheels all exist (visible in the
deploy log), and the code is plain pandas/numpy, so the risk is low — but it is not
zero and it has not been tested. If the next deploy fails on 3.14, set the Python
version in the Cloud app's Advanced settings; it cannot be pinned from the repo.

## 8. A daily file dated D holds the PREVIOUS trading day's close (2026-08-23) · DATA FACT

The filename is the write date, not the data date. Confirmed from the Apps Script
sources, which are the ground truth:

- `Script 1 (Puller)` refreshes prices at **17:45 UTC = 23:15 IST**
  (`essential1a: Core price data -> static`), after the 15:30 IST market close.
- `Script 2 (Backup)` runs `SCHEDULE.DAILY` at **20:00 IST**, and `WEEKLY` at
  **21:00 IST Sunday**.

The backup therefore fires **3h15m BEFORE** that night's refresh, so it always saves
what was pulled the previous night. File dated D holds day D-1's close.

Measured against the Sunday weekly snapshots (which hold Friday's close, markets
being shut Sat/Sun), % of prices identical within 0.5%:

| daily file dated | match |
|---|---|
| previous Thursday | 19% |
| previous Friday | 36% |
| **previous Saturday** | **100%** |
| **next Monday** | **100%** |
| next Tuesday | 23% |

So `Stocks_Daily_2026-03-09` (a Monday) contains the close of Friday 2026-03-06:
its sheet was last refreshed Sunday 23:15 IST, and a Sunday refresh returns Friday's
close because the market was shut. The Sunday weekly file matches for the same reason
(last refreshed Saturday 23:15 IST -> also Friday's close), which is exactly why the
two are 100% identical.

**Do NOT "fix" the schedule.** Making a file dated D hold day D's close would need the
backup to run inside the 45-minute window between 23:15 IST and midnight - fragile, and
it would make every new snapshot incomparable with the 52 already collected. For a
frozen 26-week experiment, changing the measurement mid-flight is worse than an offset
that is consistent and now documented.

**Consequence:** anything that joins daily files on their filename date is off by one
trading day, and a forward return built that way is shifted a full session — the
class of bug that made the old Wave/Trajectory backtests unfalsifiable. The weekly
path is unaffected: `core/panel.py` uses only the weekly archive, where the Sunday
label and the Friday close it carries are a fixed, consistent pair.

**Also:** the two archives never overlap by date. Daily holds Mon-Fri (plus 7
Saturdays), weekly holds Sundays. Zero of the 52 weekly dates appear in the daily
folder, so nothing is duplicated between them.

**Why weekly is still the training set** (asked 2026-08-23): daily starts 2026-03-04,
weekly starts 2025-08-30 -- 186 extra days. And for a 4-week label, consecutive daily
rows overlap 96% (27 of 28 days shared), so they are near-copies, not new evidence:
~6 independent windows from daily against ~12 from weekly. Daily's real value is
elsewhere -- it is the only source that can show WHEN a -20% trailing stop triggered,
which Sunday-only data structurally cannot see (weekly closes overstate stop
performance by up to 22pp/yr).
