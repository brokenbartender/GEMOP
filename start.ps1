param(
  [string]$Profile = 'full',
  [ValidateSet('base','core','full','max')]
  [string]$ConfigProfile = '',
  [switch]$Online,
  [Alias('Triad')]
  [switch]$Council, # Multi-agent council mode (canonical name). Alias: -Triad (legacy)
  [switch]$Brain, # Canonical: Sovereign Brain + Executive Core
  [switch]$Mouth, # Single interactive terminal -> NeuralBus -> Executive Core (recommended day-to-day)
  [switch]$AutoApplyPatches, # Council mode: auto-apply ```diff blocks (fail-closed) after implementation rounds.
  [switch]$StopOthers, # Stop prior agent processes before starting a new council run.
  [string]$Team = "Architect,Engineer,Tester", # Council mode: CSV team roles (used when -Agents=0).
  [int]$Agents = 0, # Council mode: explicit agent count (overrides -Team roles list).
  [int]$MaxRounds = 2, # Council mode: debate rounds (debate uses R1 design, R2+ implement).
  [int]$MaxParallel = 3, # Council mode: max concurrent agent processes spawned.
  [int]$AgentTimeoutSec = 900, # Council mode: max wall time per agent process (prevents hangs).
  [int]$QuotaCloudCalls = 0, # Council mode: global cloud call budget (optional).
  [int]$QuotaCloudCallsPerAgent = 0, # Council mode: per-agent cloud call budget (optional).
  [int]$CloudSeats = 3, # Council mode: only first N agents may use cloud when -Online.
  [int]$MaxLocalConcurrency = 2, # Council mode: cap concurrent local Ollama calls (quota-cliff safety).
  [switch]$FailClosedOnThreshold, # Council mode: exit non-zero if the run scores below -Threshold.
  [int]$Threshold = 70, # Council mode: quality threshold when -FailClosedOnThreshold is set.
  [switch]$Resume, # Council mode: skip agents already completed for the round.
  [switch]$ExtractDecisions, # Council mode: extract DECISION_JSON blocks into run state.
  [switch]$RequireDecisionJson, # Council mode: stop run if DECISION_JSON is missing.
  [switch]$VerifyAfterPatches, # Council mode: run verification pipeline after implementation rounds.
  [switch]$AdaptiveConcurrency, # Council mode: reduce parallelism when overload/latency is detected.
  [string]$ResearchUrls = "", # Council mode: safe URL fetch before Round 1 (when -Online).
  [string]$ResearchUrlsFile = "", # Council mode: file of URLs (one per line) to fetch before Round 1.
  [switch]$SaveTokens,
  [switch]$Dashboard,
  [switch]$SkipDocCheck,
  [switch]$SkipPreflight,
  [string]$Prompt
)

$ErrorActionPreference = 'Stop'
$RepoRoot = $PSScriptRoot
Set-Location $RepoRoot

# 0. Bootstrap git hooks (repo-local) so guardrails work on fresh clones.
try {
    if (Test-Path -LiteralPath (Join-Path $RepoRoot ".git")) {
        if (Test-Path -LiteralPath (Join-Path $RepoRoot ".githooks")) {
            & git config core.hooksPath .githooks | Out-Null
        }
        if (Test-Path -LiteralPath (Join-Path $RepoRoot ".gitmessage.txt")) {
            & git config commit.template .gitmessage.txt | Out-Null
        }
    }
} catch { }

# 0. Docs guardrail (refresh + validate)
try {
    $docScript = (Join-Path $RepoRoot 'scripts\\check_docs.ps1')
    $docArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $docScript, "-Fix")
    if ($SkipDocCheck) { $docArgs += "-Skip" }
    & powershell @docArgs | Out-Null
} catch {
    Write-Error ("[Docs] Failed: {0}. Re-run with -SkipDocCheck to bypass." -f $_.Exception.Message)
    exit 1
}

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
$log = Join-Path $RepoRoot "gemini.log"

if ($SaveTokens) { $env:GEMINI_SAVE_TOKENS = 'true' }

Write-Host "== GEMINI OP: MARKET READY V1.0 ==" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot" -ForegroundColor Gray

# 1b. Assemble active config (portable: base + profile + local overlay)
$resolvedProfile = $ConfigProfile
if (-not $resolvedProfile) { $resolvedProfile = $Profile }
if (-not (Test-Path (Join-Path $RepoRoot ("configs\\config.$resolvedProfile.toml")))) {
    $resolvedProfile = 'full'
}
$activeConfig = Join-Path $RepoRoot 'configs\\config.active.toml'
try {
    & python (Join-Path $RepoRoot 'scripts\\config_assemble.py') --repo-root $RepoRoot --config-profile $resolvedProfile --out $activeConfig *>> $log
    $env:GEMINI_CONFIG = $activeConfig
    Write-Host "Config: $resolvedProfile -> $activeConfig" -ForegroundColor Gray
} catch {
    Write-Warning "Config assemble failed: $($_.Exception.Message). Falling back to configs\\config.local.toml"
    $env:GEMINI_CONFIG = Join-Path $RepoRoot "configs\\config.local.toml"
}

# 2. Start Daemons
if (Test-Path ".\start-daemons.ps1") {
    Write-Host "[Init] Starting Daemons..." -ForegroundColor Green
    & .\start-daemons.ps1 -Profile $Profile *>> $log
}

# 2b. Preflight health checks (fail-fast on missing deps). Skip with -SkipPreflight.
if (-not $SkipPreflight) {
    try {
        $health = Join-Path $RepoRoot "scripts\\health.ps1"
        if (Test-Path -LiteralPath $health) {
            if ($Online) { $env:GEMINI_OP_HEALTH_REQUIRE_OLLAMA = "" } else { $env:GEMINI_OP_HEALTH_REQUIRE_OLLAMA = "1" }
            & powershell -NoProfile -ExecutionPolicy Bypass -File $health -Profile $Profile | Out-Null
        }
    } catch {
        Write-Error ("[Preflight] Failed: {0}. Re-run with -SkipPreflight to bypass." -f $_.Exception.Message)
        exit 1
    }
}

# 3. Model & Mode Selection
$Model = "ollama/phi4"
if ($Online) { $Model = "gpt-5.2-gemini" }

if ($Brain) {
    Write-Host "[Mode] SOVEREIGN BRAIN (Canonical)" -ForegroundColor Cyan
    $brainScript = (Join-Path $RepoRoot "scripts\\sovereign_brain.py")
    if (-not (Test-Path -LiteralPath $brainScript)) {
        Write-Error "[Mode] -Brain requested but missing scripts\\sovereign_brain.py. Use -Council or default mode, or add the optional Brain modules."
        exit 1
    }
    & python $brainScript
    exit $LASTEXITCODE
}

if ($Mouth) {
    Write-Host "[Mode] MOUTH (Single Terminal)" -ForegroundColor Cyan
    $mouthScript = (Join-Path $RepoRoot "scripts\\mouth.py")
    if (-not (Test-Path -LiteralPath $mouthScript)) {
        Write-Error "[Mode] -Mouth requested but missing scripts\\mouth.py. Use -Council or default mode, or add the optional Mouth modules."
        exit 1
    }
    # Default to free/local chat for the mouth. Use -Online to allow cloud hybrid routing.
    if ($Online) {
        $env:GEMINI_OP_LLM_MODE = 'hybrid'
    } else {
        $env:GEMINI_OP_LLM_MODE = 'local'
    }
    # Fast chat + stronger planning (both free/local unless LLM_MODE enables cloud).
    if (-not $env:GEMINI_OP_OLLAMA_MODEL_CHAT) { $env:GEMINI_OP_OLLAMA_MODEL_CHAT = 'phi3:mini' }
    if (-not $env:GEMINI_OP_OLLAMA_MODEL_PLAN) { $env:GEMINI_OP_OLLAMA_MODEL_PLAN = 'phi4' }
    & python $mouthScript
    exit $LASTEXITCODE
}

if ($Council) {
    Write-Host "[Mode] COUNCIL ORCHESTRATOR (Multi-Agent)" -ForegroundColor Cyan
    $ExecPath = Join-Path $RepoRoot "scripts\\triad_orchestrator.ps1"
    if (-not (Test-Path -LiteralPath $ExecPath)) {
        throw "Missing orchestrator: $ExecPath"
    }

    # Default behavior: stop any prior runs before spawning a new council.
    if (-not $PSBoundParameters.ContainsKey('StopOthers') -or $StopOthers) {
        try {
            $StopScript = Join-Path $RepoRoot "scripts\\stop_agents.ps1"
            if (Test-Path -LiteralPath $StopScript) {
                Write-Host "[Init] Stopping prior agents (killswitch)..." -ForegroundColor Yellow
                & powershell -NoProfile -ExecutionPolicy Bypass -File $StopScript | Out-Null
                # Clear repo-level STOP flags so the new run can proceed.
                & powershell -NoProfile -ExecutionPolicy Bypass -File $StopScript -ClearStopFlags | Out-Null
            }
        } catch { }
    }

    $args = @(
        "-RepoRoot", $RepoRoot,
        "-CouncilPattern", "debate",
        "-Team", "$Team",
        "-Agents", "$Agents",
        "-MaxRounds", "$MaxRounds",
        "-EnableCouncilBus",
        "-InjectLearningHints",
        "-MaxParallel", "$MaxParallel",
        "-AgentTimeoutSec", "$AgentTimeoutSec",
        "-AgentsPerConsole", "2",
        "-CloudSeats", "$CloudSeats",
        "-MaxLocalConcurrency", "$MaxLocalConcurrency"
    )
    if ($FailClosedOnThreshold) { $args += @("-FailClosedOnThreshold", "-Threshold", "$Threshold") }
    if ($Online) { $args += "-Online" }
    if ($AutoApplyPatches) { $args += "-AutoApplyPatches" }
    if ($Resume) { $args += "-Resume" }
    if ($ExtractDecisions) { $args += "-ExtractDecisions" }
    if ($RequireDecisionJson) { $args += "-RequireDecisionJson" }
    if ($VerifyAfterPatches) { $args += "-VerifyAfterPatches" }
    if ($AdaptiveConcurrency) { $args += "-AdaptiveConcurrency" }
    if ($ResearchUrls) { $args += @("-ResearchUrls", $ResearchUrls) }
    if ($ResearchUrlsFile) { $args += @("-ResearchUrlsFile", $ResearchUrlsFile) }
    if ($QuotaCloudCalls -gt 0) { $args += @("-QuotaCloudCalls", "$QuotaCloudCalls") }
    if ($QuotaCloudCallsPerAgent -gt 0) { $args += @("-QuotaCloudCallsPerAgent", "$QuotaCloudCallsPerAgent") }
    if ($Prompt) { $args += @("-Prompt", $Prompt) }

    & powershell -NoProfile -ExecutionPolicy Bypass -File $ExecPath @args
    exit $LASTEXITCODE
}

Write-Host "[Mode] SINGLE AGENT (Gemini CLI)" -ForegroundColor Green
Write-Host "[Loop] Starting Gemini CLI..." -ForegroundColor Cyan
while ($true) {
    try {
        if ($Prompt) {
            & gemini --yolo --model $Model -p $Prompt
            $Prompt = $null # Clear after first run
        } else {
            & gemini --yolo --model $Model
        }
    } catch {
        Write-Error "Gemini crashed: $_"
    }
    Write-Host "Restarting in 5s..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 5
}


