param(
  [string]$Profile = 'full',
  [switch]$Online,
  [switch]$Triad, # New: Activates 3-agent autonomous mode
  [switch]$SaveTokens,
  [switch]$Dashboard,
  [string]$Prompt
)

$ErrorActionPreference = 'Stop'
$RepoRoot = $PSScriptRoot
Set-Location $RepoRoot

# 0. Start Dashboard
if ($Dashboard) {
    Write-Host "[UI] Starting Mission Control Dashboard..." -ForegroundColor Green
    Start-Process -FilePath "streamlit" -ArgumentList @("run", "$PSScriptRoot\scripts\dashboard.py", "--server.port", "8501", "--server.headless", "true", "--browser.gatherUsageStats=false") -WindowStyle Hidden
    Write-Host " -> Accessible at: http://localhost:8501" -ForegroundColor Gray

    Write-Host "[Init] Starting Deputy Chat Processor..." -ForegroundColor Green
    Start-Process -FilePath "python" -ArgumentList @("$PSScriptRoot\scripts\deputy_chat_processor.py", "$RepoRoot") -WindowStyle Hidden
}

# 1. Environment Setup
$env:GEMINI_OP_REPO_ROOT = $RepoRoot
$env:GEMINI_CONFIG = Join-Path $RepoRoot "config.local.toml"
$log = Join-Path $RepoRoot "gemini.log"

if ($SaveTokens) { $env:GEMINI_SAVE_TOKENS = 'true' }

Write-Host "== GEMINI OP: MARKET READY V1.0 ==" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot" -ForegroundColor Gray

# 2. Start Daemons
if (Test-Path ".\start-daemons.ps1") {
    Write-Host "[Init] Starting Daemons..." -ForegroundColor Green
    & .\start-daemons.ps1 -Profile $Profile *>> $log
}

# 3. Model & Mode Selection
$Model = "ollama/phi4"
if ($Online) { $Model = "gpt-5.2-gemini" }

if ($Triad) {
    Write-Host "[Mode] TRIAD COUNCIL (Multi-Agent)" -ForegroundColor Cyan
    $ExecPath = Join-Path $RepoRoot "scripts\gemini_orchestrator.ps1"
} else {
    Write-Host "[Mode] SINGLE AGENT" -ForegroundColor Green
}

# 4. Autonomous Loop
Write-Host "[Loop] Starting Autonomous Agent..." -ForegroundColor Cyan
while ($true) {
    try {
        if ($Triad) {
            # Triad Orchestrator handles its own model routing based on config
            & $ExecPath -RepoRoot $RepoRoot -CouncilPattern debate -EnableCouncilBus -Prompt $Prompt
            $Prompt = $null # Clear after first run
        } else {
                    if ($Prompt) {
            & gemini --yolo --model $Model -p $Prompt
            $Prompt = $null # Clear after first run
        } else {
            & gemini --yolo --model $Model
        }
        }
    } catch {
        Write-Error "Gemini crashed: $_"
    }
    Write-Host "Restarting in 5s..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 5
}


