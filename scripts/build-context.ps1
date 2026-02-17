param(
  [Parameter(Mandatory = $true)]
  [string]$Query,

  [string]$RepoRoot = "",

  [int]$MaxMatches = 25
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = ($env:GEMINI_OP_REPO_ROOT)
}
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$out = Join-Path $RepoRoot 'ramshare\learning\context\current.md'
$distilled = Join-Path $RepoRoot 'ramshare\notes\distilled'
$raw = Join-Path $RepoRoot 'ramshare\notes\raw'

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

