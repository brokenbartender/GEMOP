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
  [int]$Agents = 0,
  [int]$MaxRounds = 2,
  [int]$MaxParallel = 3,
  [int]$AgentTimeoutSec = 900,

  [switch]$AutoApplyPatches,
  [switch]$AutoApplyMcpCapabilities,
  [switch]$VerifyAfterPatches,
  [switch]$AdaptiveConcurrency,
  [switch]$Autonomous,
  [switch]$RequireApproval,
  [switch]$RequireGrounding,

  # Optional: Round-1 web research (DDG search -> fetch) when -Online is set.
  [string]$ResearchQuery = "",
  [int]$ResearchMaxResults = 8,

  # Hybrid safety: prevent quota cliff -> local stampede.
  [int]$CloudSeats = 3,
  [int]$CodexSeats = 0,
  [int]$MaxLocalConcurrency = 2,
  [int]$QuotaCloudCalls = 0,
  [int]$QuotaCloudCallsPerAgent = 0,

  # Self-heal: re-run only failing seats to repair missing DECISION_JSON before stopping.
  [int]$ContractRepairAttempts = 1,

  # Skill bridge tuning
  [int]$MaxSkills = 14,
  [int]$SkillCharBudget = 45000,
  [switch]$NoAutoSelectSkills,

  [string]$Team = "Architect,Engineer,Tester",
  [switch]$AutoTeam,
  [int]$MaxTeamSize = 7,

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

function Test-OllamaAvailable {
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2
    return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
  } catch {
    return $false
  }
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

# Dynamic team composition should be the default for the "single prompt -> best execution" flow.
$enableAutoTeam = $false
if ($AutoTeam) {
  $enableAutoTeam = $true
} elseif (-not $PSBoundParameters.ContainsKey('Agents') -and -not $PSBoundParameters.ContainsKey('Team')) {
  $enableAutoTeam = $true
}
if ($enableAutoTeam) {
  $Agents = 0
}

# Hybrid safety: if online and local Ollama is unavailable, avoid creating local-only seats by default.
if ($Online) {
  $ollamaOk = Test-OllamaAvailable
  if (-not $ollamaOk) {
    $estimatedAgents = 0
    if ($enableAutoTeam) {
      $estimatedAgents = [Math]::Max(1, [int]$MaxTeamSize)
    } elseif ($Agents -gt 0) {
      $estimatedAgents = [Math]::Max(1, [int]$Agents)
    } else {
      $teamCount = @(($Team -split ",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }).Count
      $estimatedAgents = [Math]::Max(1, [int]$teamCount)
    }

    $cloudSeatsExplicit = $PSBoundParameters.ContainsKey('CloudSeats')
    $localConcurrencyExplicit = $PSBoundParameters.ContainsKey('MaxLocalConcurrency')

    if (-not $cloudSeatsExplicit -and $CloudSeats -lt $estimatedAgents) {
      Write-Host ("[Summon] Ollama unavailable; increasing CloudSeats {0} -> {1}" -f $CloudSeats, $estimatedAgents) -ForegroundColor Yellow
      $CloudSeats = $estimatedAgents
    } elseif ($CloudSeats -lt $estimatedAgents) {
      Write-Host ("[Summon] Warning: Ollama unavailable and CloudSeats={0} < estimated_agents={1}; some seats may fail." -f $CloudSeats, $estimatedAgents) -ForegroundColor Yellow
    }

    if (-not $localConcurrencyExplicit -and $MaxLocalConcurrency -gt 0) {
      Write-Host ("[Summon] Ollama unavailable; setting MaxLocalConcurrency {0} -> 0" -f $MaxLocalConcurrency) -ForegroundColor Yellow
      $MaxLocalConcurrency = 0
    }
  }
}

$autoSkills = $true
if ($NoAutoSelectSkills) {
  $autoSkills = $false
} elseif ($Task -match "(?i)\b(fidelity|portfolio|stock|stocks|market|trading|ticker|economy|earnings)\b") {
  # Finance prompts perform better with direct research context than generic external skill packs.
  $autoSkills = $false
}

$args = @(
  "-RepoRoot", $RepoRoot,
  "-RunDir", $RunDir,
  "-Prompt", $Task,
  "-CouncilPattern", "debate",
  "-Team", "$Team",
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
  "-CodexSeats", "$CodexSeats",
  "-MaxLocalConcurrency", "$MaxLocalConcurrency",
  "-QuotaCloudCalls", "$QuotaCloudCalls",
  "-QuotaCloudCallsPerAgent", "$QuotaCloudCallsPerAgent",
  "-ContractRepairAttempts", "$ContractRepairAttempts"
)

if ($autoSkills) {
  $args += @("-AutoSelectSkills", "-MaxSkills", "$MaxSkills", "-SkillCharBudget", "$SkillCharBudget")
}

if ($Online) { $args += "-Online" }
if ($AutoApplyPatches) { $args += "-AutoApplyPatches" }
if ($AutoApplyMcpCapabilities) { $args += "-AutoApplyMcpCapabilities" }
if ($VerifyAfterPatches) { $args += "-VerifyAfterPatches" }
if ($AdaptiveConcurrency) { $args += "-AdaptiveConcurrency" }
if ($Autonomous) { $args += "-Autonomous" }
if ($RequireApproval) { $args += "-RequireApproval" }
if ($RequireGrounding) { $args += "-RequireGrounding" }
if ($enableAutoTeam) { $args += @("-AutoTeam", "-MaxTeamSize", "$MaxTeamSize") }
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
