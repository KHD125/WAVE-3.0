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
