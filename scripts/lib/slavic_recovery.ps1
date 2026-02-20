<#
.SYNOPSIS
Slavic Recovery Protocol: Dead & Living Water.
Heals broken system bodies and restores vital state.
#>

[CmdletBinding()]
param(
    [string]$RunDir = ""
)

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

Write-Host "[Slavic Recovery] Initiating Protocol..." -ForegroundColor Cyan

# --- PHASE 1: DEAD WATER (Structural Repair) ---
Write-Host "[Phase 1] Applying Dead Water: Repairing the Body..." -ForegroundColor Gray

# 1. Fix missing/corrupted configs
& python scripts/config_assemble.py

# 2. Check Python syntax in scripts
Write-Host " -> Verifying script integrity..."
python -m compileall -q scripts mcp

# 3. Clear stale locks
if ($RunDir -and (Test-Path $RunDir)) {
    $locks = Get-ChildItem -Path $RunDir -Filter "*.lock" -Recurse
    foreach ($l in $locks) { Remove-Item $l.FullName -Force }
}

# --- PHASE 2: LIVING WATER (State Restoration) ---
Write-Host "[Phase 2] Applying Living Water: Restoring the Spirit..." -ForegroundColor Yellow

# 1. Restart Daemons
& .\stop-daemons.ps1
& .\start-daemons.ps1 -Profile full

# 2. Reset Stop Flags
& .\scripts\stop_agents.ps1 -ClearStopFlags

Write-Host "[Slavic Recovery] Protocol Complete. The system is revived." -ForegroundColor Green
