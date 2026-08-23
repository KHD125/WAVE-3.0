# WAVE 3.1 — the Sunday freeze, run locally.
#
# The same three steps .github/workflows/weekly.yml performs, for when GitHub
# Actions is unavailable. Register it with Task Scheduler and the experiment stops
# depending on anyone remembering:
#
#   Register-ScheduledTask -TaskName "WAVE 3.1 weekly freeze" `
#     -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 11pm) `
#     -Action  (New-ScheduledTaskAction -Execute "powershell.exe" `
#               -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PWD\tools\weekly.ps1`"") `
#     -Description "Freezes the weekly forecast to logs/waves_log.csv"
#
# Runs only when the PC is on — GitHub's runner does not care, which is why it
# stays the preferred host. This is the fallback, not the design.
#
# Exit codes: 0 success (or nothing new to log) · 1 the run failed.

$ErrorActionPreference = "Stop"
$repo   = Split-Path -Parent $PSScriptRoot
$python = Join-Path (Split-Path -Parent $repo) ".venv\Scripts\python.exe"
$stamp  = (Get-Date -Format "yyyy-MM-dd")

Set-Location $repo
if (-not (Test-Path $python)) {
    Write-Error "Python not found at $python — check the venv path."
    exit 1
}

Write-Host "WAVE 3.1 weekly freeze — $stamp" -ForegroundColor Cyan
& $python -m tools.weekly_run
if ($LASTEXITCODE -ne 0) {
    # weekly_run already printed WHY. Never swallow it: a weekly job that fails
    # quietly leaves a permanent hole in the February evidence.
    Write-Error "Forecast run failed (exit $LASTEXITCODE) — nothing frozen."
    exit 1
}

# Commit only if the log actually grew. A re-run on an already-logged snapshot is
# a legitimate outcome, not an error.
git add logs/waves_log.csv
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "no new forecast rows — log unchanged" -ForegroundColor Yellow
    exit 0
}

git -c user.name="wave-local" -c user.email="local@wave" commit -m "log: forecast frozen $stamp"
git push
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Commit succeeded but push failed — the forecast IS frozen locally. Push when you can."
    exit 0
}
Write-Host "frozen and pushed." -ForegroundColor Green
exit 0
