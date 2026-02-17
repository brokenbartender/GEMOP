<#
.SYNOPSIS
Robust council launcher that avoids command-line quoting issues.

.DESCRIPTION
Use this script when you need to run a council with a long prompt that includes spaces,
quotes, or PowerShell metacharacters (like '&'). Provide the prompt via -PromptFile.

This script is safe to run directly or via Start-Process for detached execution.
#>

[CmdletBinding()]
param(
  # Note: $PSScriptRoot is not reliable inside param default expressions in Windows PowerShell.
  # Compute RepoRoot after parameter binding instead.
  [string]$RepoRoot = "",
  [Parameter(Mandatory=$true)][string]$PromptFile,

  [switch]$Online,
  [switch]$AutoApplyPatches,
  [switch]$EnableCouncilBus,

  [string]$Team = "Chairman,Architect,Engineer,RedTeam,QA",
  [int]$MaxRounds = 2,
  [int]$MaxParallel = 2,
  [int]$CloudSeats = 2,
  [int]$MaxLocalConcurrency = 2,
  [int]$AgentTimeoutSec = 240,
  [int]$QuotaCloudCalls = 0,
  [int]$QuotaCloudCallsPerAgent = 0,

  [string]$RunDir = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
} else {
  $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
}
$PromptFile = (Resolve-Path -LiteralPath $PromptFile).Path
$prompt = Get-Content -LiteralPath $PromptFile -Raw

if ([string]::IsNullOrWhiteSpace($prompt)) {
  throw "Prompt file is empty: $PromptFile"
}

# Optional: fast-local routing knobs for hybrid stability (caller may override).
if ([string]::IsNullOrWhiteSpace($env:GEMINI_OP_ENABLE_FAST_LOCAL)) { $env:GEMINI_OP_ENABLE_FAST_LOCAL = "1" }
if ([string]::IsNullOrWhiteSpace($env:GEMINI_OP_OLLAMA_MODEL_FAST)) { $env:GEMINI_OP_OLLAMA_MODEL_FAST = "phi3:mini" }

$orch = Join-Path $RepoRoot "scripts\\triad_orchestrator.ps1"
if (-not (Test-Path -LiteralPath $orch)) {
  throw "Missing orchestrator: $orch"
}

$args = @(
  "-RepoRoot", $RepoRoot,
  "-CouncilPattern", "debate",
  "-Team", $Team,
  "-MaxRounds", "$MaxRounds",
  "-MaxParallel", "$MaxParallel",
  "-CloudSeats", "$CloudSeats",
  "-MaxLocalConcurrency", "$MaxLocalConcurrency",
  "-AgentTimeoutSec", "$AgentTimeoutSec",
  "-Prompt", $prompt
)

if ($RunDir) { $args += @("-RunDir", $RunDir) }
if ($Online) { $args += "-Online" }
if ($AutoApplyPatches) { $args += "-AutoApplyPatches" }
if ($EnableCouncilBus) { $args += "-EnableCouncilBus" }
if ($QuotaCloudCalls -gt 0) { $args += @("-QuotaCloudCalls", "$QuotaCloudCalls") }
if ($QuotaCloudCallsPerAgent -gt 0) { $args += @("-QuotaCloudCallsPerAgent", "$QuotaCloudCallsPerAgent") }

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $orch @args
exit $LASTEXITCODE
