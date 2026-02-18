<#
.SYNOPSIS
Orchestrates phases 22-27: retry learning loop, world model refresh, and verification.
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

if (-not $RunDir) {
  throw "RunDir is required"
}

$retry = Join-Path $RepoRoot "scripts\phase_24_retry_loop.ps1"
$world = Join-Path $RepoRoot "scripts\world_model_snapshot.py"
$verify = Join-Path $RepoRoot "scripts\gemini_verify.py"

if (-not (Test-Path -LiteralPath $retry)) { throw "Missing $retry" }
if (-not (Test-Path -LiteralPath $world)) { throw "Missing $world" }
if (-not (Test-Path -LiteralPath $verify)) { throw "Missing $verify" }

# Phase 24 retry learning loop
$retryArgs = @(
  "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $retry,
  "-RepoRoot", $RepoRoot,
  "-RunDir", $RunDir,
  "-Threshold", $Threshold,
  "-MaxReruns", $MaxReruns,
  "-MaxParallel", $MaxParallel,
  "-AgentsPerConsole", $AgentsPerConsole
)
if ($AutoApplyMcpCapabilities) { $retryArgs += "-AutoApplyMcpCapabilities" }
& powershell @retryArgs

# Phase 27 world-model snapshot
& python $world --refresh
if ($LASTEXITCODE -ne 0) { throw "world model refresh failed" }

# Verify phase 22-27 roadmap gates
& python $verify --check roadmap --strict
if ($LASTEXITCODE -ne 0) { throw "phase 22-27 roadmap verification failed" }

Write-Host "[phase22-27] complete"
