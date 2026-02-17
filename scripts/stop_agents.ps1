<#
.SYNOPSIS
Stop currently-running Gemini-OP agent processes (best-effort) and set STOP flags.

.DESCRIPTION
This is the "killswitch" operators should use before starting a fresh council run.
It works in two layers:
1) Write STOP files that cooperative agents check.
2) Best-effort terminate processes whose command line appears to reference this repo and agent runner scripts.

This script is intentionally conservative: it targets only processes that reference the repo root (or repo folder name)
in the command line to avoid killing unrelated shells.
#>

[CmdletBinding()]
param(
  [switch]$ClearStopFlags,
  [int]$WaitSeconds = 2
)

$ErrorActionPreference = 'SilentlyContinue'

$RepoRoot = $env:GEMINI_OP_REPO_ROOT
if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
$RepoMarker = Split-Path $RepoRoot -Leaf

$stop1 = Join-Path $RepoRoot 'STOP_ALL_AGENTS.flag'
$stop2 = Join-Path $RepoRoot 'ramshare\state\STOP'

function Write-StopFlags {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $stop2) | Out-Null
  Set-Content -LiteralPath $stop1 -Value "STOP`r`n" -Encoding UTF8
  Set-Content -LiteralPath $stop2 -Value "STOP`r`n" -Encoding UTF8
  Write-Host "[STOP] Wrote: $stop1"
  Write-Host "[STOP] Wrote: $stop2"
}

function Clear-StopFlags {
  Remove-Item -LiteralPath $stop1 -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $stop2 -Force -ErrorAction SilentlyContinue
  Write-Host "[STOP] Cleared repo-level STOP flags"
}

if ($ClearStopFlags) {
  Clear-StopFlags
  exit 0
}

Write-StopFlags

# Best-effort process termination (repo-scoped).
$targets = @("python.exe","pythonw.exe","node.exe","pwsh.exe","powershell.exe","gemini.exe","streamlit.exe")
$patterns = @(
  "scripts\\agent_runner_v2.py",
  "scripts\\triad_orchestrator.ps1",
  "run-agent",
  ".agent-jobs\\job-TRIAD-"
)

try {
  $procs = Get-CimInstance Win32_Process -ErrorAction Stop |
    Where-Object {
      $_.Name -in $targets -and $_.ProcessId -ne $PID -and $_.CommandLine -and (
        $_.CommandLine -like "*$RepoRoot*" -or $_.CommandLine -like "*$RepoMarker*"
      )
    }

  foreach ($p in $procs) {
    $cmd = [string]$p.CommandLine
    $hit = $false
    foreach ($pat in $patterns) {
      if ($cmd -like "*$pat*") { $hit = $true; break }
    }
    if (-not $hit) { continue }
    try {
      Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
      Write-Host ("[KILL] pid={0} name={1}" -f $p.ProcessId, $p.Name)
    } catch { }
  }
} catch { }

if ($WaitSeconds -gt 0) {
  Start-Sleep -Seconds $WaitSeconds
}

# Cleanup: remove stale local-slot locks left behind by hard-killed agent_runner processes.
# These locks are per-run-dir and can cause a council round to "freeze" until timeout.
try {
  $jobsRoot = Join-Path $RepoRoot '.agent-jobs'
  if (Test-Path -LiteralPath $jobsRoot) {
    $jobDirs = Get-ChildItem -LiteralPath $jobsRoot -Directory -ErrorAction SilentlyContinue
    $cleared = 0
    foreach ($d in $jobDirs) {
      $slots = Join-Path $d.FullName 'state\\local_slots'
      if (-not (Test-Path -LiteralPath $slots)) { continue }
      $locks = Get-ChildItem -LiteralPath $slots -Filter 'slot*.lock' -File -ErrorAction SilentlyContinue
      foreach ($l in $locks) {
        try {
          Remove-Item -LiteralPath $l.FullName -Force -ErrorAction SilentlyContinue
          $cleared++
        } catch { }
      }
    }
    if ($cleared -gt 0) {
      Write-Host ("[CLEAN] Removed stale local slot locks: {0}" -f $cleared)
    }
  }
} catch { }

Write-Host "[STOP] Done."
exit 0
