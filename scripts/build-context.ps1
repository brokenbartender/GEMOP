param(
  [Parameter(Mandatory = $true)]
  [string]$Query,

  [int]$MaxMatches = 25
)

$ErrorActionPreference = 'Stop'

$repoRoot = 'C:\Gemini'
$out = Join-Path $repoRoot 'ramshare\learning\context\current.md'
$distilled = Join-Path $repoRoot 'ramshare\notes\distilled'
$raw = Join-Path $repoRoot 'ramshare\notes\raw'

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $out) | Out-Null

if (!(Get-Command rg -ErrorAction SilentlyContinue)) {
  Write-Error "ripgrep (rg) not found; install rg or use semantic-search."
  exit 1
}

$stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')

$header = @(
  "# Context Pack",
  "",
  "Generated: $stamp",
  "Query: $Query",
  "",
  "Sources searched:",
  "- $distilled",
  "- $raw",
  ""
)

$matches = @()
if (Test-Path $distilled) {
  $matches += (rg -n --no-heading --color never -S --max-count $MaxMatches $Query $distilled 2>$null)
}
if (Test-Path $raw) {
  $matches += (rg -n --no-heading --color never -S --max-count $MaxMatches $Query $raw 2>$null)
}

$body = @("## Matches", "")
if (-not $matches) {
  $body += "(none)"
} else {
  foreach ($m in ($matches | Select-Object -First $MaxMatches)) {
    $body += "- $m"
  }
}

Set-Content -Path $out -Value (($header + $body) -join "`n") -NoNewline -Encoding UTF8
Write-Host "WROTE: $out"

