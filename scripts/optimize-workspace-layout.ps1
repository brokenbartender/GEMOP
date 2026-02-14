param(
  [string]$RepoRoot = 'C:\Gemini'
)

$ErrorActionPreference = 'Stop'

function Ensure-Dir([string]$Path) {
  if (!(Test-Path $Path)) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
  }
}

function Move-IfExists([string]$From, [string]$To) {
  if (!(Test-Path $From)) { return }
  Ensure-Dir (Split-Path -Parent $To)
  if (Test-Path $To) {
    $fromContent = Get-Content -Raw $From
    if (-not [string]::IsNullOrWhiteSpace($fromContent)) {
      Add-Content -Path $To -Value $fromContent
    }
    Remove-Item -Force $From
    return
  }
  Move-Item -Force -Path $From -Destination $To
}

if (!(Test-Path $RepoRoot)) {
  throw "Repo root not found: $RepoRoot"
}

$dirs = @(
  (Join-Path $RepoRoot 'logs'),
  (Join-Path $RepoRoot 'logs\sync'),
  (Join-Path $RepoRoot 'state'),
  (Join-Path $RepoRoot 'state\locks'),
  (Join-Path $RepoRoot 'ramshare\state'),
  (Join-Path $RepoRoot 'ramshare\state\audit'),
  (Join-Path $RepoRoot 'ramshare\strategy'),
  (Join-Path $RepoRoot 'ramshare\evidence'),
  (Join-Path $RepoRoot 'ramshare\evidence\inbox'),
  (Join-Path $RepoRoot 'ramshare\evidence\processed'),
  (Join-Path $RepoRoot 'ramshare\evidence\rejected'),
  (Join-Path $RepoRoot 'ramshare\evidence\staging'),
  (Join-Path $RepoRoot 'ramshare\evidence\drafts'),
  (Join-Path $RepoRoot 'ramshare\evidence\posted'),
  (Join-Path $RepoRoot 'ramshare\templates'),
  (Join-Path $RepoRoot 'ramshare\notes'),
  (Join-Path $RepoRoot 'ramshare\resources')
)

foreach ($d in $dirs) { Ensure-Dir $d }

Move-IfExists -From (Join-Path $RepoRoot 'logs\ramshare-sync.log') -To (Join-Path $RepoRoot 'logs\sync\ramshare-sync.log')
Move-IfExists -From (Join-Path $RepoRoot 'state\ramshare-sync.lock') -To (Join-Path $RepoRoot 'state\locks\ramshare-sync.lock')
Move-IfExists -From (Join-Path $RepoRoot 'ramshare_watch_state.json') -To (Join-Path $RepoRoot 'state\ramshare_watch_state.json')

Write-Host "Workspace layout optimized at: $RepoRoot"
Write-Host "- Logs: $(Join-Path $RepoRoot 'logs\sync')"
Write-Host "- Locks: $(Join-Path $RepoRoot 'state\locks')"
Write-Host "- Shared data: $(Join-Path $RepoRoot 'ramshare')"
