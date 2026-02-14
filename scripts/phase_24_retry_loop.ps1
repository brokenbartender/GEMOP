<#
.SYNOPSIS
Retry loop wrapper around the triad orchestrator.
#>

#Requires -Version 5.1

[CmdletBinding()]
param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
  [string]$RunDir,
  [int]$Threshold = 70,
  [int]$MaxReruns = 2,
  [int]$MaxParallel = 3,
  [int]$AgentsPerConsole = 2,
  [switch]$AutoApplyMcpCapabilities
)

Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot 'lib\common.ps1')

$ErrorActionPreference = "Stop"

function Read-LearningSummary([string]$Path) {
  if (-not (Test-Path $Path)) { return $null }
  try { return (Get-Content $Path -Raw | ConvertFrom-Json) } catch { return $null }
}

if (-not $RunDir) { throw "RunDir is required" }
$resolvedRunDir = (Resolve-Path -LiteralPath $RunDir).Path
$orchestrator = Join-Path $RepoRoot "scripts\triad_orchestrator.ps1"
if (-not (Test-Path -LiteralPath $orchestrator)) { throw "Missing orchestrator: $orchestrator" }

for ($i = 0; $i -le $MaxReruns; $i++) {
  Write-Host "[phase24] attempt=$i run_dir=$resolvedRunDir"
  $args = @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $orchestrator,
    "-RepoRoot", $RepoRoot,
    "-RunDir", $resolvedRunDir,
    "-EnableCouncilBus",
    "-CouncilPattern", "debate",
    "-InjectLearningHints",
    "-InjectCapabilityContract",
    "-RequireCouncilDiscussion",
    "-FailClosedOnThreshold",
    "-Threshold", $Threshold,
    "-MaxParallel", $MaxParallel,
    "-AgentsPerConsole", $AgentsPerConsole
  )
  if ($AutoApplyMcpCapabilities) { $args += "-AutoApplyMcpCapabilities" }

  & powershell @args
  $summaryPath = Join-Path $resolvedRunDir "learning-summary.json"
  $summary = Read-LearningSummary $summaryPath
  if (-not $summary) {
    Write-Host "[phase24] missing learning summary"
    continue
  }

  $avg = [double]$summary.avg_score
  Write-Host "[phase24] avg_score=$avg threshold=$Threshold"
  if ($avg -ge $Threshold) {
    Write-Host "[phase24] PASS"
    exit 0
  }
}

throw "[phase24] failed to reach threshold after $MaxReruns reruns"
