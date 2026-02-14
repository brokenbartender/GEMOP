Write-Host "?? Starting Nightly Operations (3 AM Build)..." -ForegroundColor Cyan

$RepoRoot = $PSScriptRoot\..
$log = Join-Path $RepoRoot "logs\nightly.log"

# 1. Update World Model (Codebase Mapping)
Write-Host "[1/3] Mapping codebase..."
python scripts\world_model_snapshot.py --root $RepoRoot *>> $log

# 2. Audit Dependencies
Write-Host "[2/3] Auditing environment..."
python -m pip list --outdated *>> $log

# 3. Clean stale logs
Write-Host "[3/3] Purging temporary caches..."
Remove-Item (Join-Path $RepoRoot "ramshare\state\queue\leases.json") -ErrorAction SilentlyContinue

Write-Host "? Nightly Maintenance Complete." -ForegroundColor Green
