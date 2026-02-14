param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
  [int]$IntervalSeconds = 90,
  [int]$MaxCycles = 0,
  [int]$AgentCount = 4,
  [int]$MaxParallel = 2,
  [int]$AgentsPerConsole = 2,
  [int]$Threshold = 70
)

$ErrorActionPreference = "Stop"

function Log-Line([string]$Message) {
  $ts = Get-Date -Format o
  $line = "[$ts] $Message"
  Write-Host $line
  Add-Content -Path $script:LoopLog -Value $line
}

function New-RunPrompt([string]$Role) {
@"
Role: $Role
Task: Improve Gemini-op by finding one concrete high-impact improvement and validating with repo evidence.
Rules:
1) Must cite exact file paths.
2) Must include one implementation step and one verification command.
3) Output must include a strict ranked table with headers:
   Priority | Action | Why | Exact files | Verification command
4) Include at least 5 ranked rows.
5) Include a section named "Final Output" with:
   - Completed edits
   - Verification commands
   - Remaining risks
6) End with COMPLETED.
7) Include council protocol lines:
   VERIFIED: <one validated finding from another role>
   CHALLENGED: <one corrected finding from another role>
   Council Round Summary:
   - verified_count: <n>
   - challenged_count: <n>
   - key_disagreement_resolved: <text>
"@
}

function Initialize-Run([string]$BaseRepo, [int]$Count) {
  $runId = "self-improve-" + (Get-Date -Format "yyyyMMdd-HHmmss")
  $runDir = Join-Path (Join-Path $BaseRepo ".agent-jobs") $runId
  New-Item -ItemType Directory -Path $runDir -Force | Out-Null

  $roles = @(
    "Reliability Engineer",
    "Safety Engineer",
    "Observability Engineer",
    "Autonomy Engineer",
    "Performance Engineer",
    "Quality Verifier",
    "Queue/Lease Engineer",
    "Policy/Governance Engineer"
  )

  for ($i = 1; $i -le $Count; $i++) {
    $role = $roles[($i - 1) % $roles.Count]
    $promptPath = Join-Path $runDir ("prompt{0}.txt" -f $i)
    Set-Content -Path $promptPath -Value (New-RunPrompt -Role $role) -Encoding UTF8

    $script = @"
`$ErrorActionPreference='Continue'
Get-Content -Raw '$runDir\prompt$i.txt' | Gemini exec -C '$BaseRepo' --output-last-message '$runDir\agent$i.md' --skip-git-repo-check --json 2>&1 | Tee-Object -FilePath '$runDir\agent$i.log'
"@
    Set-Content -Path (Join-Path $runDir ("run-agent{0}.ps1" -f $i)) -Value $script -Encoding UTF8
  }

  return $runDir
}

if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
  throw "Not a git repo: $RepoRoot"
}

$stateDir = Join-Path $RepoRoot "ramshare\state\self-improve"
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
$script:LoopLog = Join-Path $stateDir "self-improve-loop.log"
$loopState = Join-Path $stateDir "self-improve-loop-state.json"
$stopFlag = Join-Path $stateDir "STOP_SELF_IMPROVE.flag"
$globalStop1 = Join-Path $RepoRoot "STOP_ALL_AGENTS.flag"
$globalStop2 = Join-Path $RepoRoot "ramshare\state\STOP"
$orchestrator = Join-Path $RepoRoot "scripts\agent_batch_orchestrator.ps1"
$preflight = Join-Path $RepoRoot "scripts\GEMINI_preflight.py"

$cycle = 0
$consecutiveFailures = 0
Log-Line "self-improve loop started repo=$RepoRoot"

while ($true) {
  if ((Test-Path $stopFlag) -or (Test-Path $globalStop1) -or (Test-Path $globalStop2)) {
    Log-Line "stop flag detected; exiting loop"
    break
  }

  $cycle += 1
  if ($MaxCycles -gt 0 -and $cycle -gt $MaxCycles) {
    Log-Line "max cycles reached ($MaxCycles); exiting loop"
    break
  }

  try {
    if (Test-Path $preflight) {
      & python $preflight --prompt "self improvement cycle $cycle"
      if ($LASTEXITCODE -ne 0) {
        throw "preflight failed"
      }
    }

    $runDir = Initialize-Run -BaseRepo $RepoRoot -Count $AgentCount
    Log-Line "cycle=$cycle run_dir=$runDir"

    & powershell -NoProfile -ExecutionPolicy Bypass -File $orchestrator `
      -RepoRoot $RepoRoot `
      -RunDir $runDir `
      -EnableCouncilBus `
      -CouncilPattern voting `
      -AutoTuneFromLearning `
      -InjectLearningHints `
      -FailClosedOnThreshold `
      -Threshold $Threshold `
      -MaxParallel $MaxParallel `
      -AgentsPerConsole $AgentsPerConsole

    if ($LASTEXITCODE -ne 0) {
      throw "orchestrator failed"
    }

    $consecutiveFailures = 0
    $state = [ordered]@{
      ts = (Get-Date -Format o)
      cycle = $cycle
      run_dir = $runDir
      status = "ok"
    }
    $state | ConvertTo-Json -Depth 8 | Set-Content -Path $loopState -Encoding UTF8
    Log-Line "cycle=$cycle completed"
  } catch {
    $consecutiveFailures += 1
    Log-Line "cycle=$cycle failed error=$($_.Exception.Message)"
    $state = [ordered]@{
      ts = (Get-Date -Format o)
      cycle = $cycle
      status = "failed"
      consecutive_failures = $consecutiveFailures
      error = "$($_.Exception.Message)"
    }
    $state | ConvertTo-Json -Depth 8 | Set-Content -Path $loopState -Encoding UTF8

    if ($consecutiveFailures -ge 3) {
      Log-Line "failure threshold reached; opening self-improve circuit breaker"
      Set-Content -Path (Join-Path $stateDir "CIRCUIT_OPEN.flag") -Value "OPEN $(Get-Date -Format o)" -Encoding UTF8
      break
    }
  }

  Start-Sleep -Seconds $IntervalSeconds
}

Log-Line "self-improve loop stopped"
