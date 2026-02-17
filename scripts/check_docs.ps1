param(
  # If set, regenerate docs/APP_STATUS.md before checking.
  [switch]$Fix,

  # Skip checks (emergency escape hatch).
  [switch]$Skip
)

$ErrorActionPreference = 'Stop'

if ($Skip) {
  Write-Host "[Docs] Skipped (requested)."
  exit 0
}

$repoRoot = $env:GEMINI_OP_REPO_ROOT
if (-not $repoRoot) {
  $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
Set-Location $repoRoot

function Require-Command([string]$Name) {
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if (-not $cmd) {
    throw "Missing required command: $Name"
  }
  return $cmd.Source
}

$python = Require-Command 'python'

if ($Fix) {
  & $python scripts/update_app_status.py | Out-Null
}

& $python scripts/update_app_status.py --check | Out-Null

# Hard fail if docs contain machine-specific paths.
$patterns = @(
  'C:\\Gemini',
  'C:\\Users\\codym'
)

$rg = Get-Command rg -ErrorAction SilentlyContinue
if ($rg) {
  foreach ($p in $patterns) {
    & rg -n -S $p docs README.md 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
      throw "Docs contain machine-specific path pattern: $p"
    }
  }
} else {
  # Fallback: best-effort PowerShell scan.
  $targets = @(
    (Join-Path $repoRoot 'docs'),
    (Join-Path $repoRoot 'README.md')
  )
  foreach ($p in $patterns) {
    foreach ($t in $targets) {
      if (Test-Path $t) {
        $hits = Select-String -Path $t -Pattern $p -SimpleMatch -Recurse -ErrorAction SilentlyContinue
        if ($hits) {
          throw "Docs contain machine-specific path pattern: $p"
        }
      }
    }
  }
}

Write-Host "[Docs] OK"

# Soft warning if the docs-sync pre-commit hook is not enabled.
try {
  $git = Get-Command git -ErrorAction SilentlyContinue
  if ($git) {
    & git rev-parse --is-inside-work-tree 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
      $hooksPath = (& git config core.hooksPath 2>$null).Trim()
      if (-not $hooksPath -or ($hooksPath -ne '.githooks' -and $hooksPath -ne '.\\.githooks')) {
        Write-Host "[Docs] WARNING: pre-commit doc sync hook is not enabled. Run: git config core.hooksPath .githooks"
      }
    }
  }
} catch {
  # Non-fatal.
}
exit 0
