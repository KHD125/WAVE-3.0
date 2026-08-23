# WAVE 3.1 - the Sunday freeze, run locally.
#
# The same steps .github/workflows/weekly.yml performs, for when GitHub Actions is
# unavailable. Register it with Task Scheduler and the experiment stops depending
# on anyone remembering:
#
#   Register-ScheduledTask -TaskName "WAVE 3.1 weekly freeze" `
#     -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 11pm) `
#     -Action  (New-ScheduledTaskAction -Execute "powershell.exe" `
#               -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PWD\tools\weekly.ps1`"") `
#     -Description "Freezes the weekly forecast to logs/waves_log.csv"
#
# Runs only when the PC is on - GitHub's runner does not care, which is why it
# stays the preferred host. This is the fallback, not the design.
#
# ASCII ONLY, deliberately. Windows PowerShell 5.1 reads a .ps1 as ANSI unless the
# file carries a UTF-8 BOM. This script previously held em-dashes; under cp1252 the
# 0x94 byte decodes to a right double quote, which PowerShell honours as a string
# delimiter. Strings closed early, braces went unbalanced, and the whole file failed
# to PARSE - as a scheduled task it would have done nothing every Sunday, quietly.
# Keeping it ASCII makes the encoding irrelevant.
#
# Exit codes: 0 success (or nothing new to log) - 1 the run failed.

# NOT $ErrorActionPreference = "Stop". Under 5.1 that turns a native program's
# stderr into a terminating NativeCommandError, so a Python traceback would abort
# this script before it could read $LASTEXITCODE and report the real reason.
# Every failure below is checked explicitly instead.
$ErrorActionPreference = "Continue"

$repo   = Split-Path -Parent $PSScriptRoot
$python = Join-Path (Split-Path -Parent $repo) ".venv\Scripts\python.exe"
$stamp  = (Get-Date -Format "yyyy-MM-dd")

Set-Location $repo
if (-not (Test-Path $python)) {
    Write-Host "FAILED: python not found at $python - check the venv path." -ForegroundColor Red
    exit 1
}

Write-Host "WAVE 3.1 weekly freeze - $stamp" -ForegroundColor Cyan
& $python -m tools.weekly_run
if ($LASTEXITCODE -ne 0) {
    # weekly_run already printed WHY (a stale snapshot, a Drive failure, a bad
    # schema). Never swallow it: a weekly job that fails quietly leaves a
    # permanent hole in the February evidence.
    Write-Host "FAILED: forecast run exited $LASTEXITCODE - nothing frozen." -ForegroundColor Red
    exit 1
}

# Commit only if the log actually grew. A re-run against an already-logged
# snapshot is a legitimate outcome, not an error.
git add logs/waves_log.csv
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "no new forecast rows - log unchanged" -ForegroundColor Yellow
    exit 0
}

git -c user.name="wave-local" -c user.email="local@wave" commit -m "log: forecast frozen $stamp"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED: commit failed - the forecast is NOT recorded." -ForegroundColor Red
    exit 1
}

git push
if ($LASTEXITCODE -ne 0) {
    # The forecast IS frozen locally and timestamped; only the upload is missing.
    # That is a warning, not a failure - do not exit 1 and scare a scheduled task.
    Write-Host "WARNING: commit succeeded but push failed. The forecast IS frozen locally; push when you can." -ForegroundColor Yellow
    exit 0
}

Write-Host "frozen and pushed." -ForegroundColor Green
exit 0
