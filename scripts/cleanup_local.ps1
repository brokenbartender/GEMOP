param(
  [switch]$Apply
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $RepoRoot

$targets = @(
  (Join-Path $RepoRoot '__pycache__'),
  (Join-Path $RepoRoot '.pytest_cache'),
  (Join-Path $RepoRoot '.gemini\\tmp')
)

Write-Host "Repo: $RepoRoot"
Write-Host "Mode: " -NoNewline
if ($Apply) { Write-Host "APPLY (deleting)" -ForegroundColor Yellow } else { Write-Host "DRY-RUN" -ForegroundColor Cyan }
Write-Host ""

foreach ($t in $targets) {
  if (Test-Path -LiteralPath $t) {
    if ($Apply) {
      Remove-Item -LiteralPath $t -Recurse -Force -ErrorAction SilentlyContinue
      Write-Host "Deleted: $t"
    } else {
      Write-Host "Would delete: $t"
    }
  }
}

$globs = @('tmp_run_*', 'tmp_run_timeout_*')
foreach ($g in $globs) {
  $items = Get-ChildItem -Path $RepoRoot -Filter $g -Directory -ErrorAction SilentlyContinue
  foreach ($it in $items) {
    if ($Apply) {
      Remove-Item -LiteralPath $it.FullName -Recurse -Force -ErrorAction SilentlyContinue
      Write-Host "Deleted: $($it.FullName)"
    } else {
      Write-Host "Would delete: $($it.FullName)"
    }
  }
}

Write-Host ""
Write-Host "Done."

