# omni_god_mode.ps1 - The "God Mode" Entry Point
# This script activates all advanced autonomous layers simultaneously.

param(
    [Parameter(Mandatory=$true)][string]$Task,
    [switch]$Online = $true,
    [int]$Rounds = 3,
    [string]$Team = "Architect,Engineer,RedTeam,Auditor,Operator",
    [switch]$Autonomous = $false
)

$RepoRoot = Get-Location
$RunDir = Join-Path $RepoRoot ".agent-jobs\god_run_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
# New-Item -ItemType Directory -Path $RunDir -Force | Out-Null -> Handled by summon.ps1

# --- HARDWARE COMPATIBILITY: i5/32GB ---
$env:GEMINI_OP_OLLAMA_MODEL_DEFAULT = "phi3:mini"
$env:GEMINI_OP_MODEL_EDGE_LOCAL = "phi3:mini"

Write-Host "`n" + ("="*60) -ForegroundColor Cyan
Write-Host "      ⚡ GEMINI OP: GOD MODE ACTIVATED ⚡" -ForegroundColor Cyan
Write-Host ("="*60) -ForegroundColor Cyan

# 0. Clean Slate (Manual Killswitch)
Write-Host "[0/4] Clearing previous sessions..." -ForegroundColor Yellow
$StopScript = Join-Path $RepoRoot "scripts\stop_agents.ps1"
if (Test-Path $StopScript) {
    & pwsh -NoProfile -ExecutionPolicy Bypass -File $StopScript -ClearStopFlags
}

# 1. Start Background Power Daemons
Write-Host "[1/4] Igniting Super-Power Daemons..." -ForegroundColor Yellow
$Daemons = @(
    "scripts/observer_daemon.py",
    "scripts/recursive_meta_agent.py",
    "scripts/ai_data_factory.py",
    "scripts/telluric_resonance.py",
    "scripts/spirit_radio.py",
    "scripts/tarot_telemetry.py"
)

$ProcessIds = @()
foreach ($d in $Daemons) {
    $ScriptPath = Join-Path $RepoRoot $d
    $p = Start-Process python -ArgumentList "`"$ScriptPath`" --run-dir `"$RunDir`"" -WindowStyle Minimized -PassThru
    $ProcessIds += $p.Id
    Write-Host "  -> $(Split-Path $d -Leaf) active (PID: $($p.Id))"
}

# 2. Pre-Warm Memory
Write-Host "[2/4] Synchronizing Knowledge Base..." -ForegroundColor Yellow
& python (Join-Path $RepoRoot "scripts/memory_ingest.py") --all | Out-Null

# 3. Launch the Swarm with Full Hierarchy
Write-Host "[3/4] Summoning the High-Intelligence Swarm..." -ForegroundColor Yellow
$SummonArgs = @("-Task", $Task, "-Team", $Team, "-MaxRounds", $Rounds, "-RunDir", $RunDir)
if ($Online) { $SummonArgs += "-Online" }
$SummonArgs += "-AutoApplyPatches"
$SummonArgs += "-CloudSeats", "5" # Full swarm cloud access
$SummonArgs += @("-AgentTimeoutSec", "1200") # 20 min timeout

if (-not $Autonomous) {
    $SummonArgs += "-RequireApproval" # Security Gating
} else {
    Write-Host "  -> AUTONOMOUS MODE: Approval Gating DISABLED." -ForegroundColor Red
}

Write-Host "[Summon] Invoking Orchestrator in $RunDir..." -ForegroundColor Cyan
& pwsh -NoProfile -ExecutionPolicy Bypass -File ".\scripts\summon.ps1" @SummonArgs

# 4. Final Aggregation & Cleanup
Write-Host "[4/4] Generating Omnimodal Mission Report..." -ForegroundColor Yellow
& python (Join-Path $RepoRoot "scripts/omnimodal_mediator.py") $RunDir

Write-Host "`n" + ("="*60) -ForegroundColor Cyan
Write-Host "      🏁 MISSION COMPLETE: $(Split-Path $RunDir -Leaf)" -ForegroundColor Cyan
Write-Host "      REPORT: $RunDir\OMNIMODAL_REPORT.md" -ForegroundColor Green
Write-Host ("="*60) -ForegroundColor Cyan

# Cleanup Daemons
Write-Host "Shutting down Super-Power Daemons..." -ForegroundColor Gray
foreach ($DaemonPid in $ProcessIds) {
    Stop-Process -Id $DaemonPid -Force -ErrorAction SilentlyContinue
}
