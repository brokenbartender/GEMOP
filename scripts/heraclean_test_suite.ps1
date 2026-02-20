<#
.SYNOPSIS
The Heraclean Test Suite: 10 Rigorous Labors for Gemini OP.
Validates Physics, Governance, and Orchestration layers.
#>

$ErrorActionPreference = "Continue"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Sovereign = Join-Path $RepoRoot "scripts\sovereign.py"
$TestDir = Join-Path $RepoRoot ".agent-jobs\_heraclean_tmp"

if (Test-Path $TestDir) { Remove-Item $TestDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $TestDir | Out-Null

function Write-Header([string]$Title) {
    Write-Host "`n=== LABOR: $Title ===" -ForegroundColor Cyan
}

function Test-Command([string]$Cmd, [string]$CheckStr) {
    Write-Host "Invoking: $Cmd" -ForegroundColor Gray
    try {
        $out = Invoke-Expression $Cmd 2>&1 | Out-String
        if ($out -match $CheckStr) {
            Write-Host " [PASS] Verified '$CheckStr'" -ForegroundColor Green
            return $true
        } else {
            Write-Host " [FAIL] Missing '$CheckStr' in output." -ForegroundColor Red
            Write-Host " Output: $out" -ForegroundColor DarkGray
            return $false
        }
    } catch {
        Write-Host " [CRITICAL] Exception: $_" -ForegroundColor Red
        return $false
    }
}

# --- LABOR 1: The Schwarzschild Density (Event Horizon) ---
Write-Header "Event Horizon (Prompt Mass)"
$MassivePrompt = "Start " + ("constraint " * 100) + (" file_ref.py" * 50) + " End"
$EHScript = Join-Path $RepoRoot "scripts\event_horizon.py"
Test-Command "python $EHScript --run-dir $TestDir --prompt '$MassivePrompt' --context-radius 100" "split_required.:true"

# --- LABOR 2: The Budget Quota Cliff (Governor) ---
Write-Header "Governor Budget Block"
$GovScript = Join-Path $RepoRoot "scripts\gemini_governance.py"
$BudgetFile = Join-Path $TestDir "zero_budget.json"
Set-Content -Path $BudgetFile -Value '{"daily_limit_usd": 0.0, "spent_today_usd": 1.0, "date": "2030-01-01"}'
# Now expects "BLOCKED" on stdout
Test-Command "python $GovScript --budget-path $BudgetFile enforce --action 'test_spend' --estimated-spend-usd 0.01" "BLOCKED"

# --- LABOR 3: The Hallucination Horizon (Thermodynamics) ---
Write-Header "Thermodynamic Divergence"
$ThermoScript = Join-Path $RepoRoot "scripts\thermodynamics.py"
Test-Command "python $ThermoScript --run-dir $TestDir --mode lyapunov --round 10 --val 0.9" "HALLUCINATION HORIZON"

# --- LABOR 4: Cross-Domain Pivot (Sovereign CLI Logic) ---
Write-Header "Sovereign Cortex Integrity"
# Run without args -> triggers print_help() and banner
Test-Command "python '$Sovereign' 2>&1" "Gemini"

# --- LABOR 5: A2A Router Loopback (Distributed Intelligence) ---
Write-Header "A2A Router Loopback"
$A2AScript = Join-Path $RepoRoot "scripts\a2a_router.py"
# Regex relaxed for JSON formatting
Test-Command "python $A2AScript --route local --message 'ping' --dry-run" '"ok":\s*true'

# --- LABOR 6: Dead Water (Config Assembly) ---
Write-Header "Slavic Config Assembly"
$ConfigScript = Join-Path $RepoRoot "scripts\config_assemble.py"
$OutConfig = Join-Path $TestDir "config.test.toml"
# Now expects "Config assembled" on stdout
Test-Command "python $ConfigScript --repo-root $RepoRoot --out $OutConfig" "Config assembled"

# --- LABOR 7: Navier-Stokes Turbulence (Fluid Router) ---
Write-Header "Navier-Stokes Throttle"
Test-Command "python $ThermoScript --run-dir $TestDir --mode navier --queue 1 --val 0.0" "TURBULENCE"

# --- LABOR 8: Sword of Gryffindor (Self-Scan) ---
Write-Header "Sword of Gryffindor (Meta-Scan)"
$SwordScript = Join-Path $RepoRoot "scripts\sword_of_gryffindor.py"
Test-Command "python $SwordScript --target-repo $RepoRoot\scripts --repo-root $RepoRoot" "INNOVATIONS DETECTED"

# --- LABOR 9: HITL Gate (Safety) ---
Write-Header "Human-in-the-Loop Gate"
# Now expects "BLOCKED" on stdout
Test-Command "python $GovScript enforce --action 'nuke' --requires-human-approval" "BLOCKED"

# --- LABOR 10: Circuit Breaker Check ---
Write-Header "Circuit Breaker Logic"
$Dispatcher = Join-Path $RepoRoot "scripts\gemini_dispatcher.py"
# Clean inbox first to ensure 'No jobs found'
Remove-Item (Join-Path $TestDir "*") -Force -Recurse -ErrorAction SilentlyContinue
Test-Command "python $Dispatcher --inbox $TestDir --dry-run" "No jobs found"

Write-Host "`n=== HERACLEAN SUITE COMPLETE ===" -ForegroundColor Cyan
