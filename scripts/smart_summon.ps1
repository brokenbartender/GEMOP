<#
.SYNOPSIS
Smart wrapper for summon.ps1 that dynamically compiles the best agent team.

.DESCRIPTION
Analyzes the task prompt using `team_compiler.py` to select specialized roles
(e.g. ResearchLead, Security, Ops) instead of the default Triad.
Then invokes `summon.ps1` with the optimized team.

.EXAMPLE
.\scripts\smart_summon.ps1 -Task "Research competitors and draft a strategy doc"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Task,

    [switch]$Online,
    [switch]$AutoApplyPatches,
    [switch]$VerifyAfterPatches,
    [switch]$Yeet,
    [string]$TargetRepo = "",
    [switch]$Assimilate
)

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

Write-Host "[Smart] Analyzing task to compile the perfect team..." -ForegroundColor Cyan

# 1. Compile Team
$compilerScript = Join-Path $RepoRoot "scripts\team_compiler.py"
$useAutoTeamFallback = $false
$teamList = ""
try {
    $json = python $compilerScript --prompt "$Task"
    $data = $json | ConvertFrom-Json
} catch {
    Write-Warning "Team compiler failed, falling back to orchestrator AutoTeam: $($_.Exception.Message)"
    $useAutoTeamFallback = $true
}

if (-not $useAutoTeamFallback) {
    if (-not $data.ok -or -not $data.roles) {
        Write-Warning "Team compiler returned no usable roles, falling back to orchestrator AutoTeam."
        $useAutoTeamFallback = $true
    } else {
        $teamList = $data.roles -join ","
        Write-Host "[Smart] Selected Team: $teamList" -ForegroundColor Green
    }
}

# 2. Invoke Summon
$maxRounds = 2
if ($AutoApplyPatches -or $Task -match "architect|analyze|improve|fix|implement") {
    $maxRounds = 4
    Write-Host "[Smart] Complex task detected. Bumping MaxRounds to $maxRounds." -ForegroundColor Yellow
}

$summonArgs = @{
    Task = $Task
    Agents = 0
    MaxRounds = $maxRounds
}
if ($useAutoTeamFallback) {
    $summonArgs['AutoTeam'] = $true
} else {
    $summonArgs['Team'] = $teamList
}

if ($Online) { $summonArgs['Online'] = $true }
if ($AutoApplyPatches) { $summonArgs['AutoApplyPatches'] = $true }
if ($VerifyAfterPatches) { $summonArgs['VerifyAfterPatches'] = $true }

Write-Host "[Smart] Summoning Council..." -ForegroundColor Cyan
# Capture the output to extract RunDir if possible, or just rely on latest run directory detection
& .\scripts\summon.ps1 @summonArgs
$rc = $LASTEXITCODE

# Find the run directory we just created
$latestRunDir = (Get-ChildItem "$RepoRoot\.agent-jobs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName

# 3. Yeet (Commit & Push)
if ($Yeet -and $rc -eq 0) {
    Write-Host "[Smart] Yeeting changes..." -ForegroundColor Magenta
    $yeetArgs = @{
        RunDir = $latestRunDir
        Prompt = $Task
    }
    if (-not [string]::IsNullOrWhiteSpace($TargetRepo)) {
        $yeetArgs['TargetRepo'] = $TargetRepo
    }
    & .\scripts\yeet.ps1 @yeetArgs
}

# 4. Sword of Gryffindor (Assimilate Improvements)
if ($Assimilate -and -not [string]::IsNullOrWhiteSpace($TargetRepo)) {
    Write-Host "[Smart] Invoking Sword of Gryffindor..." -ForegroundColor Yellow
    $swordScript = Join-Path $RepoRoot "scripts\sword_of_gryffindor.py"
    & python $swordScript --target-repo $TargetRepo --repo-root $RepoRoot
}

# 5. Cleanup Daemons
Write-Host "[Smart] Cleaning up background daemons..." -ForegroundColor Yellow
$stopDaemons = Join-Path $RepoRoot "stop-daemons.ps1"
if (Test-Path $stopDaemons) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $stopDaemons | Out-Null
}
