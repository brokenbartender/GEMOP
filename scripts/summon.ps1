<#
.SYNOPSIS
Summon a council run from a single task prompt, with automatic skill selection.

.DESCRIPTION
Creates a new run directory under .agent-jobs/ and launches scripts/triad_orchestrator.ps1
with safe, high-power defaults:
- stop prior agents
- decision extraction + verify-friendly output contract
- optional hybrid routing via -Online
- auto-selected external skills (Codex + Gemini) injected into prompts

This script is the recommended "do whatever I want" entrypoint.
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [string]$Task,

  [switch]$Online,
  [int]$Agents = 3,
  [int]$MaxRounds = 2,
  [int]$MaxParallel = 3,
  [int]$AgentTimeoutSec = 900,

  [switch]$AutoApplyPatches,
  [switch]$VerifyAfterPatches,
  [switch]$AdaptiveConcurrency,

  # Optional: Round-1 web research (DDG search -> fetch) when -Online is set.
  [string]$ResearchQuery = "",
  [int]$ResearchMaxResults = 8,

  # Hybrid safety: prevent quota cliff -> local stampede.
  [int]$CloudSeats = 3,
  [int]$MaxLocalConcurrency = 2,

  # Self-heal: re-run only failing seats to repair missing DECISION_JSON before stopping.
  [int]$ContractRepairAttempts = 1,

  # Skill bridge tuning
  [int]$MaxSkills = 14,
  [int]$SkillCharBudget = 45000,

  [string]$Team = "Architect,Engineer,Tester",

  [string]$RunDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# Pre-flight: Ensure MCP daemon dependencies are installed
$daemonDir = Join-Path $RepoRoot "mcp-daemons"
if (Test-Path $daemonDir) {
  if (-not (Test-Path (Join-Path $daemonDir "node_modules"))) {
    Write-Host "[Pre-flight] Installing missing MCP daemon dependencies..." -ForegroundColor Yellow
    Push-Location $daemonDir
    try { & npm install } finally { Pop-Location }
  }
}
Set-Location $RepoRoot

function Ensure-Dir([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
  }
}

function Slug([string]$s) {
  $t = ($s -replace "[^A-Za-z0-9]+","-").Trim("-")
  if ($t.Length -gt 40) { $t = $t.Substring(0,40) }
  if ([string]::IsNullOrWhiteSpace($t)) { $t = "task" }
  return $t.ToLower()
}

# Stop other agents first (killswitch), then clear stop flags.
# Important: do this before creating a new run dir, because stop_agents writes STOP into all known run dirs.
try {
  $StopScript = Join-Path $RepoRoot "scripts\\stop_agents.ps1"
  if (Test-Path -LiteralPath $StopScript) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $StopScript | Out-Null
    & powershell -NoProfile -ExecutionPolicy Bypass -File $StopScript -ClearStopFlags | Out-Null
  }
} catch { }

if ([string]::IsNullOrWhiteSpace($RunDir)) {
  $jobs = Join-Path $RepoRoot ".agent-jobs"
  Ensure-Dir $jobs
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  $RunDir = Join-Path $jobs ("run_{0}_{1}" -f $ts, (Slug $Task))
}
Ensure-Dir $RunDir
Ensure-Dir (Join-Path $RunDir "state")

$ExecPath = Join-Path $RepoRoot "scripts\\triad_orchestrator.ps1"
if (-not (Test-Path -LiteralPath $ExecPath)) {
  throw "Missing orchestrator: $ExecPath"
}

# Auto-apply needs an implementation round. Round 1 is analysis/research, Round 2 is debate,
# so ensure at least 3 rounds when patches are expected.
if ($AutoApplyPatches -and $MaxRounds -lt 3) {
  Write-Host "[Summon] AutoApplyPatches requested; bumping MaxRounds $MaxRounds -> 3" -ForegroundColor Yellow
  $MaxRounds = 3
}

$args = @(
  "-RepoRoot", $RepoRoot,
  "-RunDir", $RunDir,
  "-Prompt", $Task,
  "-CouncilPattern", "debate",
  "-Agents", "$Agents",
  "-MaxRounds", "$MaxRounds",
  "-EnableCouncilBus",
  "-InjectLearningHints",
  "-InjectCapabilityContract",
  "-ExtractDecisions",
  "-RequireDecisionJson",
  "-MaxParallel", "$MaxParallel",
  "-AgentTimeoutSec", "$AgentTimeoutSec",
  "-CloudSeats", "$CloudSeats",
  "-MaxLocalConcurrency", "$MaxLocalConcurrency",
  "-ContractRepairAttempts", "$ContractRepairAttempts",
  "-AutoSelectSkills",
  "-MaxSkills", "$MaxSkills",
  "-SkillCharBudget", "$SkillCharBudget"
)

if ($Online) { $args += "-Online" }
if ($AutoApplyPatches) { $args += "-AutoApplyPatches" }
if ($VerifyAfterPatches) { $args += "-VerifyAfterPatches" }
if ($AdaptiveConcurrency) { $args += "-AdaptiveConcurrency" }
if ($ResearchQuery) { $args += @("-ResearchQuery", $ResearchQuery, "-ResearchMaxResults", "$ResearchMaxResults") }

Write-Host "[Summon] RunDir: $RunDir" -ForegroundColor Gray
Write-Host "[Summon] Task: $Task" -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File $ExecPath @args
$rc = $LASTEXITCODE

# Always try to generate a quick eval report for observability.
try {
  $eval = Join-Path $RepoRoot "scripts\\generate_eval_report.py"
  if (Test-Path -LiteralPath $eval) {
    & python $eval --run-dir $RunDir | Out-Null
    $evalMd = Join-Path $RunDir "state\\eval_report.md"
    if (Test-Path -LiteralPath $evalMd) {
      Write-Host ("[Summon] Eval report: {0}" -f $evalMd) -ForegroundColor Gray
    }
  }
} catch { }

# Also generate a numeric scorecard for the whole run.
try {
  $sc = Join-Path $RepoRoot "scripts\\council_scorecard.py"
  if (Test-Path -LiteralPath $sc) {
    & python $sc --run-dir $RunDir | Out-Null
    $scMd = Join-Path $RunDir "state\\scorecard.md"
    if (Test-Path -LiteralPath $scMd) {
      Write-Host ("[Summon] Scorecard: {0}" -f $scMd) -ForegroundColor Gray
    }
  }
} catch { }

exit $rc
