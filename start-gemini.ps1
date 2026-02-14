param(
  [ValidateSet('default','dev','browser','research','ops','fidelity','full','screen-readonly','screen-operator','sidecar-operator')]
  [string]$Profile = 'full',
  [switch]$NoWatchEvidence,
  [switch]$NoWatchdog,
  [switch]$StartHud = $false,
  [switch]$HudTray,
  [switch]$SaveTokens # Flag to force local models even when online
)

$RepoRoot = $PSScriptRoot
$work = Join-Path $RepoRoot 'work'
$log = Join-Path $RepoRoot 'gemini.log'
if (!(Test-Path $work)) { New-Item -ItemType Directory -Force -Path $work | Out-Null }
Set-Location $RepoRoot

if ($SaveTokens) { $env:GEMINI_SAVE_TOKENS = 'true' }

# 1. Start Evidence Watcher
if (-not $NoWatchEvidence) {
  $watchScript = Join-Path $RepoRoot 'scripts\watch-evidence.ps1'
  if (Test-Path $watchScript) {
    Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $watchScript, '-Profile', $Profile) | Out-Null
  }
}

# 2. Start Watchdog
if (-not $NoWatchdog) {
  $watchdogScript = Join-Path $RepoRoot 'scripts\start-watchdog.ps1'
  if (Test-Path $watchdogScript) {
    & $watchdogScript -Profile $Profile *>> $log
  }
}

# 3. Ensure Daemons
if ($Profile -in 'browser','research','fidelity','full') {
  & (Join-Path $RepoRoot 'start-daemons.ps1') -Profile $Profile *>> $log
}

# 4. Main Loop with Smart Model Selection
Write-Host "Starting Gemini Market-Ready v1.0 (Offline Fallback Enabled)" -ForegroundColor Green
while ($true) {
  $smartModel = python .\scripts\gemini_smart_model.py
  Write-Host "[$(Get-Date -Format o)] Selected Model: $smartModel" -ForegroundColor Cyan
  
  & gemini --yolo --model $smartModel
  
  Write-Host "Gemini exited with $LASTEXITCODE; restarting in 5s..." -ForegroundColor Yellow
  Start-Sleep -Seconds 5
}
