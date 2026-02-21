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
Write-Host "[3/5] Purging temporary caches..."
Remove-Item (Join-Path $RepoRoot "ramshare\state\queue\leases.json") -ErrorAction SilentlyContinue

# 4. Deep Memory Consolidation (HEAVY)
Write-Host "[4/5] Running deep Mycelium consolidation..."
# Use all-miniLM local models to re-index and prune
& python scripts\memory_ingest.py --all *>> $log
& python scripts\wormhole_indexer.py *>> $log

# 5. Full System Audit
Write-Host "[5/5] Generating full performance/ROI report..."
& python scripts\ai_ops_report.py *>> $log

Write-Host "✨ Nightly Maintenance Complete. System Optimized." -ForegroundColor Green
