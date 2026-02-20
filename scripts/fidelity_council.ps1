<#
.SYNOPSIS
Run a finance-focused council debate for Fidelity portfolio prompts.

.DESCRIPTION
Thin wrapper around scripts/summon.ps1 with defaults tuned for
market/event research quality:
- disables generic auto-skill injection
- enables online research
- deepens query coverage for macro + ticker catalysts
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [string]$Task,
  [switch]$Online,
  [int]$MaxRounds = 2,
  [int]$MaxParallel = 3,
  [int]$ResearchMaxResults = 12,
  [int]$CloudSeats = 7,
  [int]$MaxLocalConcurrency = 1
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Test-OllamaAvailable {
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2
    return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
  } catch {
    return $false
  }
}

$symbols = @()
$matches = [regex]::Matches($Task, '\b[A-Z]{1,5}\b')
foreach ($m in $matches) {
  $v = $m.Value.ToUpperInvariant()
  if ($v -in @("USD","US","ETF","NAV","CPI","PCE","FOMC")) { continue }
  if ($symbols -notcontains $v) { $symbols += $v }
}
$symbols = $symbols | Select-Object -First 6

$queryParts = @(
  "US economic calendar tomorrow",
  "Federal Reserve rate outlook",
  "CPI PCE jobs report schedule"
)
if ($symbols.Count -gt 0) {
  $queryParts += ("{0} earnings guidance analyst revisions" -f ($symbols -join " "))
}
$researchQuery = ($queryParts -join "; ")

$summon = Join-Path $RepoRoot "scripts\summon.ps1"
if (-not (Test-Path -LiteralPath $summon)) {
  throw "Missing script: $summon"
}

$ollamaOk = Test-OllamaAvailable
if (-not $ollamaOk) {
  if (-not $PSBoundParameters.ContainsKey("CloudSeats")) { $CloudSeats = 7 }
  if (-not $PSBoundParameters.ContainsKey("MaxLocalConcurrency")) { $MaxLocalConcurrency = 0 }
}

$args = @(
  "-Task", $Task,
  "-NoAutoSelectSkills",
  "-MaxRounds", "$MaxRounds",
  "-MaxParallel", "$MaxParallel",
  "-CloudSeats", "$CloudSeats",
  "-MaxLocalConcurrency", "$MaxLocalConcurrency",
  "-ResearchQuery", $researchQuery,
  "-ResearchMaxResults", "$ResearchMaxResults"
)
if ($Online -or -not $PSBoundParameters.ContainsKey("Online")) { $args += "-Online" }

Write-Host "[FidelityCouncil] research_query=$researchQuery" -ForegroundColor Gray
& powershell -NoProfile -ExecutionPolicy Bypass -File $summon @args
exit $LASTEXITCODE
