<#
Run N improvement cycles. Each cycle uses improve_until_100.ps1 to reach 100/100 (or best effort),
records the best run dir, then produces a batch summary at the end.
#>

[CmdletBinding()]
param(
  [int]$Cycles = 10,
  [int]$MaxAttemptsPerCycle = 5,
  [Parameter(Mandatory=$true)][string]$Task,
  [string]$ResearchQuery = "",
  [int]$Agents = 3,
  [int]$MaxRounds = 3,
  [int]$ResearchMaxResults = 10
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Ensure-Dir([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
  }
}

$batchId = Get-Date -Format "yyyyMMdd_HHmmss"
$batchDir = Join-Path (Join-Path $RepoRoot ".agent-jobs") ("batch_{0}" -f $batchId)
Ensure-Dir $batchDir

$runsFile = Join-Path $batchDir "runs.txt"
"" | Set-Content -LiteralPath $runsFile -Encoding UTF8

for ($c = 1; $c -le $Cycles; $c++) {
  $cycleTask = ("[CYCLE {0}/{1}] {2}" -f $c, $Cycles, $Task)
  Write-Host ("[Batch] cycle={0}/{1}" -f $c, $Cycles) -ForegroundColor Cyan

  $out = & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\\improve_until_100.ps1") `
    -Task $cycleTask `
    -ResearchQuery $ResearchQuery `
    -MaxAttempts $MaxAttemptsPerCycle `
    -Agents $Agents `
    -MaxRounds $MaxRounds `
    -ResearchMaxResults $ResearchMaxResults 2>&1

  # Parse best_run from improve_until_100 output.
  $best = $null
  foreach ($ln in $out) {
    if ($ln -match "^\\[Loop\\] best_run=(?<path>.+?) process=") {
      $best = $Matches["path"].Trim()
    }
  }
  if (-not $best) {
    # Fallback: last created run dir.
    $best = (Get-ChildItem (Join-Path $RepoRoot ".agent-jobs") -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
  }

  Add-Content -LiteralPath $runsFile -Value $best -Encoding UTF8
  Write-Host ("[Batch] recorded_best_run: {0}" -f $best) -ForegroundColor Gray
}

try {
  & python (Join-Path $RepoRoot "scripts\\summarize_batch.py") --runs-file $runsFile --out (Join-Path $batchDir "batch_summary.md") | Out-Null
  Write-Host ("[Batch] Summary: {0}" -f (Join-Path $batchDir "batch_summary.md")) -ForegroundColor Yellow
} catch {
  Write-Host ("[Batch] Failed to write summary: {0}" -f $_.Exception.Message) -ForegroundColor Red
}

