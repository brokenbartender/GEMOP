<#
.SYNOPSIS
Runs Gemini in a guarded, checkpointed git workflow.

.DESCRIPTION
Creates a new run branch, periodically checkpoints any working tree changes,
pushes and verifies the remote HEAD, and records artifacts in .safe-auto\runs.

This script is intended to be safe-by-default:
- waits for git locks (index.lock, etc.)
- avoids logging common secret patterns
- uses file-safe paths via Join-Path
#>

#Requires -Version 5.1

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true, HelpMessage = 'Short description of the task.')]
  [string]$Task,

  [Parameter(HelpMessage = 'Repository root path. Defaults to the repo above /scripts.')]
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,

  [Parameter(HelpMessage = 'Base branch to start from.')]
  [string]$BaseBranch = 'main',

  [Parameter(HelpMessage = 'Remote name.')]
  [string]$Remote = 'origin',

  [Parameter(HelpMessage = 'Seconds between checkpoint scans.')]
  [ValidateRange(10, 3600)]
  [int]$CheckpointSeconds = 60,

  [Parameter(HelpMessage = 'Max number of checkpoints before terminating Gemini.')]
  [ValidateRange(1, 10000)]
  [int]$MaxCheckpoints = 200,

  [Parameter(HelpMessage = 'Arguments passed to Gemini (do not include secrets).')]
  [string]$GeminiArgs = '--full-auto',

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

function Get-WorkingDeltaCount {
  $res = Invoke-GeminiGit -RepoRoot $RepoRoot -Args @('status', '--porcelain=v1') -TimeoutSec $GitTimeoutSec -Retries $GitRetries
  return [int](($res.StdOut | Measure-Object -Line).Lines)
}

function Assert-CleanBase {
  $current = Get-GitOutput @('rev-parse', '--abbrev-ref', 'HEAD')
  if ($current -ne $BaseBranch) {
    throw "Expected to start on '$BaseBranch', current branch is '$current'."
  }
  $dirtyCount = Get-WorkingDeltaCount
  if ($dirtyCount -ne 0) {
    throw "Working tree is not clean ($dirtyCount changed entries). Clean/stash first."
  }
}

function Assert-NoStopFlags {
  $flags = @(
    (Join-Path $RepoRoot 'STOP_ALL_AGENTS.flag'),
    (Join-Path $RepoRoot 'ramshare\state\STOP'),
    (Join-Path $RepoRoot 'ramshare\state\self-improve\CIRCUIT_OPEN.flag')
  )
  $found = @($flags | Where-Object { Test-Path -LiteralPath $_ })
  if ($found.Count -gt 0) {
    throw ("stale stop/circuit flags detected:`n" + ($found -join "`n"))
  }
}

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.git') -PathType Container)) {
  throw "Not a git repo: $RepoRoot"
}

Assert-GeminiCommand -CommandName 'git'
Assert-GeminiCommand -CommandName 'Gemini'
Assert-GeminiCommand -CommandName 'python'

Wait-GeminiGitLockClear -RepoRoot $RepoRoot -TimeoutSec $GitLockTimeoutSec

$safeTask = ($Task.ToLowerInvariant() -replace '[^a-z0-9\-]+', '-').Trim('-')
if ([string]::IsNullOrWhiteSpace($safeTask)) {
  throw 'Task must include letters/numbers.'
}

$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$runRoot = Join-Path $RepoRoot '.safe-auto\runs'
$runDir = Join-Path $runRoot $runId
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

Initialize-GeminiLogging -LogDirectory $runDir -LogFileName 'runner.log'

$stdoutLog = Join-Path $runDir 'Gemini.stdout.log'
$stderrLog = Join-Path $runDir 'Gemini.stderr.log'
$reportPath = Join-Path $runDir 'report.md'
$statePath = Join-Path $runDir 'state.json'
$governanceScript = Join-Path $RepoRoot 'scripts\GEMINI_governance.py'

function Invoke-GovernanceGate([string]$Action, [string]$Details) {
  if (-not (Test-Path -LiteralPath $governanceScript)) { return }
  $res = Invoke-GeminiExternalCommand -FilePath 'python' -ArgumentList @($governanceScript, 'enforce', '--action', $Action, '--details', $Details) -WorkingDirectory $RepoRoot -TimeoutSec 120
  if ($res.ExitCode -ne 0 -or $res.TimedOut) {
    throw "governance gate blocked: $Action"
  }
}

Write-GeminiLog -Level INFO -Message 'safe-auto run start'
Write-GeminiLog -Level INFO -Message ("task={0}" -f $Task)
Write-GeminiLog -Level INFO -Message ("repo={0}" -f $RepoRoot)
Write-GeminiLog -Level INFO -Message ("base_branch={0}" -f $BaseBranch)
Write-GeminiLog -Level INFO -Message ("GEMINI_args={0}" -f (Protect-GeminiSensitiveText -Text $GeminiArgs))

Exec-Git @('fetch', $Remote, '--prune')
Assert-NoStopFlags
Assert-CleanBase
Invoke-GovernanceGate -Action 'safe-auto start' -Details ("task={0} branch={1}" -f $Task, $BaseBranch)

Exec-Git @('checkout', $BaseBranch)
Exec-Git @('reset', '--hard', "$Remote/$BaseBranch")

$baseSha = Get-GitOutput @('rev-parse', '--short', 'HEAD')
$branchName = "auto/$safeTask/$runId"
Exec-Git @('checkout', '-b', $branchName)
Exec-Git @('push', '-u', $Remote, $branchName)
Write-GeminiLog -Level INFO -Message ("created run branch={0} base_sha={1}" -f $branchName, $baseSha)

$state = [ordered]@{
  run_id = $runId
  task = $Task
  repo = $RepoRoot
  base_branch = $BaseBranch
  remote = $Remote
  base_sha = $baseSha
  run_branch = $branchName
  started_at = (Get-Date -Format o)
  checkpoints = @()
}
$state | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $statePath -Encoding UTF8

$GeminiArgList = @()
if (-not [string]::IsNullOrWhiteSpace($GeminiArgs)) {
  $GeminiArgList = $GeminiArgs.Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)
}

$proc = Start-Process -FilePath 'Gemini' -ArgumentList $GeminiArgList -WorkingDirectory $RepoRoot -PassThru -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
Write-GeminiLog -Level INFO -Message ("spawned Gemini pid={0}" -f $proc.Id)

$checkpointCount = 0
$stopReason = 'Gemini-exited'
$pushFailures = 0

try {
  while (-not $proc.HasExited) {
    Start-Sleep -Seconds $CheckpointSeconds

    $dirty = Get-WorkingDeltaCount
    if ($dirty -eq 0) {
      Write-GeminiLog -Level DEBUG -Message 'checkpoint-scan: no changes'
      continue
    }

    $checkpointCount += 1
    if ($checkpointCount -gt $MaxCheckpoints) {
      $stopReason = 'max-checkpoints'
      Write-GeminiLog -Level WARN -Message ("max checkpoints reached ({0}); stopping Gemini" -f $MaxCheckpoints)
      Stop-Process -Id $proc.Id -Force
      break
    }

    Write-GeminiLog -Level INFO -Message ("checkpoint {0}: detected {1} changed entries" -f $checkpointCount, $dirty)
    Invoke-GovernanceGate -Action 'safe-auto checkpoint' -Details ("checkpoint={0} dirty={1}" -f $checkpointCount, $dirty)

    Exec-Git @('add', '-A')
    $msg = "auto($runId): checkpoint $checkpointCount`n`nTask: $Task`nRun-Id: $runId"
    Exec-Git @('commit', '-m', $msg)

    Exec-Git @('push', $Remote, $branchName)
    Exec-Git @('fetch', $Remote, $branchName)

    $localHead = Get-GitOutput @('rev-parse', '--short', 'HEAD')
    $remoteHead = Get-GitOutput @('rev-parse', '--short', "$Remote/$branchName")
    if ($localHead -ne $remoteHead) {
      $pushFailures += 1
      Write-GeminiLog -Level ERROR -Message ("push verify FAILED local={0} remote={1}" -f $localHead, $remoteHead)
      $stopReason = 'push-verify-failed'
      Stop-Process -Id $proc.Id -Force
      break
    }

    $cp = [ordered]@{
      index = $checkpointCount
      at = (Get-Date -Format o)
      local_head = $localHead
      remote_head = $remoteHead
    }
    $state.checkpoints += $cp
    $state | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $statePath -Encoding UTF8
    Write-GeminiLog -Level INFO -Message ("checkpoint {0} pushed+verified sha={1}" -f $checkpointCount, $localHead)
  }
}
finally {
  if (-not $proc.HasExited) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
  }
}

# Final checkpoint after process exits, if there are unstaged changes.
$remaining = Get-WorkingDeltaCount
if ($remaining -gt 0) {
  $checkpointCount += 1
  Write-GeminiLog -Level INFO -Message ("final checkpoint: detected {0} changed entries" -f $remaining)
  Invoke-GovernanceGate -Action 'safe-auto final-checkpoint' -Details ("checkpoint={0} dirty={1}" -f $checkpointCount, $remaining)

  Exec-Git @('add', '-A')
  $finalMsg = "auto($runId): final checkpoint`n`nTask: $Task`nRun-Id: $runId"
  try {
    Exec-Git @('commit', '-m', $finalMsg)
    Exec-Git @('push', $Remote, $branchName)
    Exec-Git @('fetch', $Remote, $branchName)

    $localHead = Get-GitOutput @('rev-parse', '--short', 'HEAD')
    $remoteHead = Get-GitOutput @('rev-parse', '--short', "$Remote/$branchName")
    if ($localHead -eq $remoteHead) {
      $state.checkpoints += [ordered]@{
        index = $checkpointCount
        at = (Get-Date -Format o)
        local_head = $localHead
        remote_head = $remoteHead
      }
      Write-GeminiLog -Level INFO -Message ("final checkpoint pushed+verified sha={0}" -f $localHead)
    } else {
      $pushFailures += 1
      Write-GeminiLog -Level ERROR -Message ("final push verify FAILED local={0} remote={1}" -f $localHead, $remoteHead)
      $stopReason = 'push-verify-failed'
    }
  } catch {
    Write-GeminiLog -Level WARN -Message ("final checkpoint failed: {0}" -f $_.Exception.Message)
  }
}

$state.finished_at = (Get-Date -Format o)
$state.stop_reason = $stopReason
$state.GEMINI_exit_code = $proc.ExitCode
$state.push_failures = $pushFailures
$state.final_head = Get-GitOutput @('rev-parse', '--short', 'HEAD')
$state | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $statePath -Encoding UTF8

$report = @(
  "# Safe Auto Run Report",
  "",
  "- Run ID: $runId",
  "- Task: $Task",
  "- Repo: $RepoRoot",
  "- Branch: $branchName",
  "- Base: $BaseBranch@$baseSha",
  "- Final HEAD: $($state.final_head)",
  "- Stop reason: $($state.stop_reason)",
  "- Gemini exit code: $($state.GEMINI_exit_code)",
  "- Push verify failures: $($state.push_failures)",
  "- Checkpoints: $($state.checkpoints.Count)",
  "",
  "## Artifacts",
  "",
  "- runner.log",
  "- Gemini.stdout.log",
  "- Gemini.stderr.log",
  "- state.json"
)
$report -join "`r`n" | Set-Content -LiteralPath $reportPath -Encoding UTF8

Write-GeminiLog -Level INFO -Message 'run complete'
Write-GeminiLog -Level INFO -Message ("report={0}" -f $reportPath)

Write-Host ""
Write-Host "Run completed. Report: $reportPath"
