<#
.SYNOPSIS
Rolls back a safe-auto run to the recorded base branch state.

.DESCRIPTION
Loads .safe-auto\runs\<RunId>\state.json and resets the repository back to the
base branch and remote recorded at run start. Optionally deletes the run branch.

This script waits for git lock files and uses safe file paths.
#>

#Requires -Version 5.1

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true, HelpMessage = 'Run ID (folder name under .safe-auto\runs).')]
  [string]$RunId,

  [Parameter(HelpMessage = 'Repository root path. Defaults to the repo above /scripts.')]
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,

  [Parameter(HelpMessage = 'Delete the remote/local run branch after rollback.')]
  [switch]$DeleteRunBranch,

  [Parameter(HelpMessage = 'Seconds to wait for git locks to clear.')]
  [ValidateRange(1, 3600)]
  [int]$GitLockTimeoutSec = 120,

  [Parameter(HelpMessage = 'Per-attempt git command timeout (seconds).')]
  [ValidateRange(10, 3600)]
  [int]$GitTimeoutSec = 300,

  [Parameter(HelpMessage = 'Retries for transient git errors.')]
  [ValidateRange(0, 10)]
  [int]$GitRetries = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'lib\common.ps1')

function Exec-Git([string[]]$Args) {
  [void](Invoke-GeminiGit -RepoRoot $RepoRoot -Args $Args -TimeoutSec $GitTimeoutSec -Retries $GitRetries)
}

function Get-GitOutput([string[]]$Args) {
  $res = Invoke-GeminiGit -RepoRoot $RepoRoot -Args $Args -TimeoutSec $GitTimeoutSec -Retries $GitRetries
  return ($res.StdOut | Out-String).Trim()
}

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.git') -PathType Container)) {
  throw "Not a git repo: $RepoRoot"
}

Assert-GeminiCommand -CommandName 'git'
Wait-GeminiGitLockClear -RepoRoot $RepoRoot -TimeoutSec $GitLockTimeoutSec

$runDir = Join-Path $RepoRoot (Join-Path '.safe-auto\runs' $RunId)
$statePath = Join-Path $runDir 'state.json'
if (-not (Test-Path -LiteralPath $statePath)) {
  throw "Missing run state: $statePath"
}

Initialize-GeminiLogging -LogDirectory $runDir -LogFileName 'rollback.log'

$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
$runBranch = [string]$state.run_branch
$baseBranch = [string]$state.base_branch
$baseSha = [string]$state.base_sha
$remote = [string]$state.remote

Write-GeminiLog -Level INFO -Message ("rollback start run_id={0} base_branch={1} base_sha={2}" -f $RunId, $baseBranch, $baseSha)

Exec-Git @('fetch', '--all', '--prune')
Exec-Git @('checkout', $baseBranch)
Exec-Git @('reset', '--hard', "$remote/$baseBranch")
Exec-Git @('clean', '-fd')

if ($DeleteRunBranch -and -not [string]::IsNullOrWhiteSpace($runBranch)) {
  try {
    Exec-Git @('branch', '-D', $runBranch)
  } catch {
    Write-GeminiLog -Level WARN -Message ("failed to delete local branch {0}: {1}" -f $runBranch, $_.Exception.Message)
  }
  try {
    Exec-Git @('push', $remote, '--delete', $runBranch)
  } catch {
    Write-GeminiLog -Level WARN -Message ("failed to delete remote branch {0}: {1}" -f $runBranch, $_.Exception.Message)
  }
}

$head = Get-GitOutput @('rev-parse', '--short', 'HEAD')

Write-GeminiLog -Level INFO -Message 'rollback complete'
Write-Host "Rollback complete."
Write-Host "Base branch: $baseBranch"
Write-Host "Expected base sha: $baseSha"
Write-Host "Current head: $head"
