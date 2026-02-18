<#
Repeat Council runs until the scorecard reaches 100/100 (process + patch), or until MaxAttempts.

This is intentionally conservative:
- It does not force destructive actions.
- It keeps Agents=3 by default for CPU-only machines.
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Task,
  [string]$ResearchQuery = "",
  [int]$MaxAttempts = 5,
  [int]$Agents = 3,
  [int]$MaxRounds = 3,
  [int]$ResearchMaxResults = 12
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Ensure-Dir([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
  }
}

function Slug([string]$s) {
  $t = ($s -replace "[^A-Za-z0-9]+","-").Trim("-")
  if ($t.Length -gt 30) { $t = $t.Substring(0,30) }
  if ([string]::IsNullOrWhiteSpace($t)) { $t = "task" }
  return $t.ToLower()
}

$best = $null
$jobs = Join-Path $RepoRoot ".agent-jobs"
Ensure-Dir $jobs
$prevScore = $null

for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  $runDir = Join-Path $jobs ("run_{0}_attempt{1}_{2}" -f $ts, $attempt, (Slug $Task))

  # Escalate strictness if we failed previously.
  $extra = ""
  if ($attempt -gt 1) {
    $prevBlock = ""
    try {
      if ($prevScore) {
        $fails = @()
        foreach ($g in $prevScore.gates) {
          if ($g.ok -ne $true) { $fails += ("{0}: {1}" -f $g.name, $g.detail) }
        }
        $prevBlock = "[PREV SCORECARD FAILURES]`n" + ($fails -join "`n") + "`n"
      }
    } catch { $prevBlock = "" }
    $extra = @"

[FEEDBACK]
$prevBlock

[STRICT PATCH DISCIPLINE]
- In implementation rounds, output diffs in `diff --git a/... b/...` format (like `git diff`).
- Do not include any prose inside ```diff blocks.
- Ensure every touched file is listed in DECISION_JSON.files.
- Hunks must have correct @@ counts (git-applyable). If unsure, regenerate the diff.
"@
  }

  $fullTask = $Task + $extra

  $args = @(
    "-Online",
    "-Agents", "$Agents",
    "-MaxRounds", "$MaxRounds",
    "-Task", $fullTask,
    "-ResearchMaxResults", "$ResearchMaxResults",
    "-AutoApplyPatches",
    "-VerifyAfterPatches",
    "-RunDir", $runDir
  )
  if ($ResearchQuery) {
    $args += @("-ResearchQuery", $ResearchQuery)
  }

  Write-Host ("[Loop] attempt={0}/{1} run_dir={2}" -f $attempt, $MaxAttempts, $runDir) -ForegroundColor Cyan
  & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\\summon.ps1") @args | Out-Null

  $scJson = Join-Path $runDir "state\\scorecard.json"
  if (-not (Test-Path -LiteralPath $scJson)) {
    & python (Join-Path $RepoRoot "scripts\\council_scorecard.py") --run-dir $runDir | Out-Null
  }
  $sc = Get-Content -LiteralPath $scJson -Raw | ConvertFrom-Json
  $prevScore = $sc
  $proc = [int]$sc.scores.process_score
  $patch = [int]$sc.scores.patch_score
  Write-Host ("[Loop] scores process={0} patch={1} perfect_100={2}" -f $proc, $patch, $sc.perfect_100) -ForegroundColor Gray

  if (-not $best -or ($proc -gt $best.proc) -or (($proc -eq $best.proc) -and ($patch -gt $best.patch))) {
    $best = @{ runDir = $runDir; proc = $proc; patch = $patch }
  }

  if ($sc.perfect_100 -eq $true) {
    Write-Host ("[Loop] SUCCESS 100/100 at: {0}" -f $runDir) -ForegroundColor Green
    break
  }
}

if ($best) {
  Write-Host ("[Loop] best_run={0} process={1} patch={2}" -f $best.runDir, $best.proc, $best.patch) -ForegroundColor Yellow
}
