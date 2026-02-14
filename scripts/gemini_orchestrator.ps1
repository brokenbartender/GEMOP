<#
.SYNOPSIS
Gemini OP triad orchestrator (market-ready hardened).
.DESCRIPTION
Resolves a run directory, normalizes run scripts for deterministic invocation,
optionally injects prompt/protocol contracts, launches run-agent scripts with
safe parallelism and timeouts, then runs post-run learning steps.
#>

#Requires -Version 5.1

[CmdletBinding()]
param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
  [string]$RunDir = "",
  [int]$MaxParallel = 3,
  [int]$Threshold = 70,
  [string]$RawGeminiPath = "C:\nvm4w\nodejs\Gemini.cmd",
  [int]$AgentsPerConsole = 2,
  [switch]$EnableCouncilBus,
  [ValidateSet("voting", "debate", "hierarchical")]
  [string]$CouncilPattern = "debate",
  [switch]$AutoTuneFromLearning,
  [switch]$InjectLearningHints,
  [switch]$InjectCapabilityContract,
  [switch]$AutoApplyMcpCapabilities,
  [switch]$FailClosedOnThreshold,
  [switch]$RequireCouncilDiscussion,
  [int]$MaxAgentRuntimeSeconds = 1800,
  [int]$MaxEffectiveParallel = 6,
  [switch]$NoLaunch,
  [Parameter(HelpMessage = 'Seconds to wait for git locks (index.lock, etc.) to clear.')]
  [ValidateRange(1, 3600)]
  [int]$GitLockTimeoutSec = 120,

  [Parameter(HelpMessage = 'Timeout for the close-loop learning step (seconds).')]
  [ValidateRange(60, 86400)]
  [int]$CloseLoopTimeoutSec = 1800,

  [Parameter(HelpMessage = 'Timeout for auxiliary python post-steps (seconds).')]
  [ValidateRange(30, 86400)]
  [int]$AuxPythonTimeoutSec = 900,

  [Parameter(HelpMessage = 'Optional directory for orchestrator logs (defaults to RunDir).')]
  [string]$LogDirectory = '',

  [Parameter(HelpMessage = 'PowerShell executable for launching run-agent scripts (auto-detected by default).')]
  [string]$PowerShellExe = '',

  [Parameter(HelpMessage = 'The mission prompt/brief for the Agent Foundry.')]
  [string]$Prompt = ''

)

Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot 'lib\common.ps1')

$ErrorActionPreference = "Stop"

function Log-Line([string]$Message) {
  Write-GeminiLog -Level INFO -Message $Message
}

function Run-AgentFoundry([string]$BaseRepo, [string]$MissionPrompt, [string]$TargetRunDir) {
  if ([string]::IsNullOrWhiteSpace($MissionPrompt)) {
    Log-Line "Foundry: No mission prompt provided, skipping specialist formulation."
    return
  }
  $foundryScript = Join-Path $BaseRepo "scripts\agent_foundry.py"
  if (-not (Test-Path -LiteralPath $foundryScript)) {
    Log-Line "Foundry: Script missing at $foundryScript"
    return
  }
  
  Log-Line "Foundry: Running check for specialized roles..."
  # We use the current session's python to run the foundry
  $res = Invoke-GeminiExternalCommand -FilePath 'python' -ArgumentList @($foundryScript, '--mission', $MissionPrompt, '--run-dir', $TargetRunDir) -WorkingDirectory $BaseRepo -TimeoutSec 300
  
  if ($res.ExitCode -eq 0) {
    foreach ($line in $res.StdOut.Split("`n")) {
      if ($line -match "MISSION_TEAM: (.*)") {
        $team = $matches[1].Trim()
        Log-Line "Foundry: Team formulation: $team"
        # Optional: write to a file for the dashboard
        $teamPath = Join-Path $TargetRunDir "mission_team.txt"
        $team | Set-Content -Path $teamPath -Encoding UTF8
      }
      if ($line -match "Foundry: (.*)") {
        Log-Line $line.Trim()
      }
    }
  } else {
    Log-Line "Foundry: Failed with exit code $($res.ExitCode)"
    Log-Line $res.StdErr
  }
}

<#
.SYNOPSIS
Resolve the run directory to operate on.

.DESCRIPTION
If -RunDir is empty, selects the newest directory under <RepoRoot>\.agent-jobs.
#>
function Resolve-RunDir([string]$Base, [string]$Requested) {
  if (-not [string]::IsNullOrWhiteSpace($Requested)) {
    $p = Resolve-Path -LiteralPath $Requested -ErrorAction Stop
    return $p.Path
  }


  $jobsRoot = Join-Path $Base ".agent-jobs"
  if (-not (Test-Path -LiteralPath $jobsRoot -PathType Container)) {
    throw "Missing jobs root: $jobsRoot"
  }
  $latest = Get-ChildItem -LiteralPath $jobsRoot -Directory -ErrorAction Stop | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $latest) {
    throw "No run directories found under: $jobsRoot"
  }
  return $latest.FullName
}

function Resolve-PowerShellExe([string]$Requested) {
  <#
  .SYNOPSIS
  Resolves the PowerShell executable used to run agent scripts.
  #>
  if (-not [string]::IsNullOrWhiteSpace($Requested)) { return $Requested }
  $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
  if ($pwsh) { return $pwsh.Source }
  $ps = Get-Command powershell -ErrorAction SilentlyContinue
  if ($ps) { return $ps.Source }
  return 'powershell'
}




function Load-EfficiencyModel([string]$BaseRepo) {
  $p = Join-Path $BaseRepo "ramshare\state\learning\efficiency_model.json"
  if (-not (Test-Path -LiteralPath $p)) { return $null }
  try {
    return (Get-Content -LiteralPath $p -Raw | ConvertFrom-Json)
  } catch {
    return $null
  }
}

function Get-SafeParallelCap([int]$RequestedCap) {
  $cpu = 4
  try {
    if ($env:NUMBER_OF_PROCESSORS) {
      $cpu = [int]$env:NUMBER_OF_PROCESSORS
    }
  } catch {}
  $cpuCap = [Math]::Max(1, [Math]::Floor($cpu / 2))
  return [Math]::Max(1, [Math]::Min($RequestedCap, $cpuCap))
}

function Inject-PromptLearningHints([string]$BaseRepo, [string]$TargetRunDir) {
  function Sanitize-Hint([string]$Text) {
    if ([string]::IsNullOrWhiteSpace($Text)) { return $null }
    $t = $Text.Trim()
    $t = $t -replace "[`r`n`t]", " "
    $t = $t -replace "[\u0000-\u001F]", ""
    $t = $t.Replace('"', "'")
    $t = $t -replace '```', ""
    if ($t.Length -gt 220) { $t = $t.Substring(0, 220) }
    if ($t -match "^(Require|Force|Disallow|Enforce|Use|State|All recommendations|Before final write)") {
      return $t
    }
    return $null
  }

  $hintLines = @()
  $qualityModel = Join-Path $BaseRepo "ramshare\state\learning\quality_model.json"
  if (Test-Path $qualityModel) {
    try {
      $qm = Get-Content -LiteralPath $qualityModel -Raw | ConvertFrom-Json
      foreach ($h in ($qm.prompt_hints | Where-Object { $_ -and $_.Trim().Length -gt 0 })) {
        $clean = Sanitize-Hint $h
        if ($clean) { $hintLines += "- $clean" }
      }
    } catch {}
  }
  $councilManifest = Join-Path $TargetRunDir "council-manifesto.json"
  if (Test-Path $councilManifest) {
    try {
      $cm = Get-Content -LiteralPath $councilManifest -Raw | ConvertFrom-Json
      if ($cm.updated_prompt_snippet) {
        $clean = Sanitize-Hint ([string]$cm.updated_prompt_snippet)
        if ($clean) { $hintLines += "- $clean" }
      }
    } catch {}
  }
  if (-not $hintLines -or $hintLines.Count -eq 0) { return 0 }
  $block = "`n`n### Learned Prompt Hints`n" + (($hintLines | Select-Object -Unique) -join "`n") + "`n"
  $changed = 0
  $prompts = Get-ChildItem $TargetRunDir -File -Filter "prompt*.txt" | Sort-Object Name
  foreach ($p in $prompts) {
    $text = Get-Content $p.FullName -Raw
    if ($text -notlike "*### Learned Prompt Hints*") {
      Set-Content -LiteralPath $p.FullName -Value ($text + $block) -Encoding UTF8
      $changed += 1
    }
  }
  return $changed
}

function Inject-CapabilityRequestContract([string]$TargetRunDir) {
  $block = @"

### Capability Discovery Contract
If you are blocked by missing capabilities, append a section exactly named `Capability Requests` and list only needed items:
- `skill: <name> | reason: <why>`
- `mcp: <name> | reason: <why>`
- `tool: <command> | reason: <why>`

Only request capabilities you actually need for this run.
"@
  $changed = 0
  $prompts = Get-ChildItem $TargetRunDir -File -Filter "prompt*.txt" | Sort-Object Name
  foreach ($p in $prompts) {
    $text = Get-Content $p.FullName -Raw
    if ($text -notlike "*Capability Discovery Contract*") {
      Set-Content -LiteralPath $p.FullName -Value ($text + "`n" + $block + "`n") -Encoding UTF8
      $changed += 1
    }
  }
  return $changed
}

function Inject-CouncilProtocolContract([string]$TargetRunDir, [string]$Pattern) {
  $block = @"

### Council Communication Contract
You are part of a council pattern: $Pattern
Rules:
1) Before final output, publish at least one `VERIFIED` response to another agent finding.
2) Before final output, publish at least one `CHALLENGED` response with a concrete correction.
3) Include a `Council Round Summary` section listing:
   - verified_count
   - challenged_count
   - key_disagreement_resolved
4) If no disagreement exists, challenge assumptions with one edge case anyway.
"@
  $changed = 0
  $prompts = Get-ChildItem $TargetRunDir -File -Filter "prompt*.txt" | Sort-Object Name
  foreach ($p in $prompts) {
    $text = Get-Content $p.FullName -Raw
    if ($text -notlike "*Council Communication Contract*") {
      Set-Content -LiteralPath $p.FullName -Value ($text + "`n" + $block + "`n") -Encoding UTF8
      $changed += 1
    }
  }
  return $changed
}

function Validate-CouncilManifestContract([string]$TargetRunDir) {
  $manifest = Join-Path $TargetRunDir "council-manifesto.json"
  if (-not (Test-Path $manifest)) { return }
  $obj = $null
  try {
    $obj = Get-Content $manifest -Raw | ConvertFrom-Json
  } catch {
    throw "Invalid council-manifesto.json (json parse failed): $manifest"
  }
  if (-not $obj) {
    throw "Invalid council-manifesto.json (empty): $manifest"
  }
  $missing = @()
  if ([string]::IsNullOrWhiteSpace([string]$obj.stop_doing)) { $missing += "stop_doing" }
  if ([string]::IsNullOrWhiteSpace([string]$obj.start_doing)) { $missing += "start_doing" }
  if ([string]::IsNullOrWhiteSpace([string]$obj.updated_prompt_snippet)) { $missing += "updated_prompt_snippet" }
  if ($missing.Count -gt 0) {
    throw ("Council manifesto missing required fields: " + ($missing -join ", "))
  }
}

<#
.SYNOPSIS
Normalize run-agent*.ps1 scripts for deterministic raw Gemini invocation.

.DESCRIPTION
Rewrites wrapper calls and normalizes output encoding redirections.
#>
function Normalize-RunScriptsForRawGemini([string]$TargetRunDir, [string]$RawPath, [string]$LaunchFormat = "raw_GEMINI_cmd_exec") {
  $scripts = Get-ChildItem -LiteralPath $TargetRunDir -File -Filter "run-agent*.ps1" -ErrorAction SilentlyContinue | Sort-Object Name
  if (-not $scripts) { return 0 }
  if (-not (Test-Path -LiteralPath $RawPath)) {
    throw "Raw Gemini path not found: $RawPath"
  }

  $changed = 0
  foreach ($s in $scripts) {
    $text = Get-Content -LiteralPath $s.FullName -Raw
    if ([string]::IsNullOrWhiteSpace($text)) { continue }

    # Rewrite "Gemini exec" invocations to explicit raw CLI path so wrappers cannot intercept.
    $rewritten = $text.Replace("Gemini exec", "& `"$RawPath`" exec")
    # Normalize occasional smart quotes that can break script parsing.
    $rewritten = $rewritten.Replace([char]0x201C, '"').Replace([char]0x201D, '"')
    $rewritten = $rewritten.Replace([char]0x2018, "'").Replace([char]0x2019, "'")

    if ($LaunchFormat -eq "raw_GEMINI_cmd_exec_strict_quote") {
      # Force explicit call operator form in case a script has an unquoted raw path.
      $escapedPath = [regex]::Escape($RawPath)
      $rewritten = [regex]::Replace($rewritten, "(?i)\b$escapedPath\s+exec\b", "& `"$RawPath`" exec")
    }

    # Ensure agent markdown output is written as UTF-8, not PowerShell's UTF-16 default via `>`.
    $rewritten = [regex]::Replace(
      $rewritten,
      ">\s*(\.agent-jobs[^\r\n]*agent\d+\.md)",
      "| Out-File -FilePath `$1 -Encoding utf8"
    )

    if ($rewritten -ne $text) {
      Set-Content -LiteralPath $s.FullName -Value $rewritten -Encoding UTF8
      $changed += 1
    }
  }

  return $changed
}

function Inject-MirrorContext([string]$BaseRepo, [string]$TargetRunDir) {
  $lessonsPath = Join-Path $BaseRepo "ramshare\learning\memory\lessons.md"
  $memorySummary = "No recent tactical memory."
  if (Test-Path $lessonsPath) {
    $lines = Get-Content $lessonsPath
    $lessons = $lines | Where-Object { $_.Trim().StartsWith("- ") }
    if ($lessons) {
      $memorySummary = ($lessons | Select-Object -Last 3) -join " | "
    }
  }

  $packPath = Join-Path $BaseRepo "agents\packs\triad_autonomous.json"
  $roles = @("architect", "engineer", "tester") # Fallback
  if (Test-Path $packPath) {
    try {
      $pack = Get-Content $packPath -Raw | ConvertFrom-Json
      $roles = $pack.roles.role_id
    } catch {}
  }

  $prompts = Get-ChildItem $TargetRunDir -File -Filter "prompt*.txt" | Sort-Object Name
  $i = 0
  foreach ($p in $prompts) {
    $role = if ($i -lt $roles.Count) { $roles[$i] } else { "specialist" }
    $roleFile = Join-Path $BaseRepo "agents\roles\$role.md"
    $identity = if (Test-Path $roleFile) { Get-Content $roleFile -Raw } else { "You are a specialist agent." }
    
    $block = @"

### MIRROR PROTOCOL (Universal Self-Awareness)
You are $role. 
Here is your identity file:
$identity

Here is your recent memory (Tactical Lessons):
$memorySummary
"@
    $text = Get-Content $p.FullName -Raw
    if ($text -notlike "*### MIRROR PROTOCOL*") {
      Set-Content -LiteralPath $p.FullName -Value ($text + "`n" + $block) -Encoding UTF8
      Log-Line "Mirror Protocol injected for $role (prompt$($i+1))"
    }
    $i++
  }
}

function Test-RunScriptParsing([string]$TargetRunDir) {
  $scripts = Get-ChildItem $TargetRunDir -File -Filter "run-agent*.ps1" | Sort-Object Name
  $failed = @()
  foreach ($s in $scripts) {
    $ok = $true
    try {
      [void][scriptblock]::Create((Get-Content -LiteralPath $s.FullName -Raw))
    } catch {
      $ok = $false
    }
    if (-not $ok) { $failed += $s.FullName }
  }
  return $failed
}

function Initialize-CouncilBus([string]$BaseRepo, [string]$TargetRunDir, [string]$Pattern, [int]$AgentCount) {
  $busScript = Join-Path $BaseRepo "scripts\council_bus.py"
  if (-not (Test-Path -LiteralPath $busScript)) {
    throw "Missing council bus script: $busScript"
  }
  $res = Invoke-GeminiExternalCommand -FilePath 'python' -ArgumentList @($busScript, 'init', '--run-dir', $TargetRunDir, '--pattern', $Pattern, '--agents', $AgentCount, '--max-rounds', '3') -WorkingDirectory $BaseRepo -TimeoutSec $AuxPythonTimeoutSec
  if ($res.ExitCode -ne 0 -or $res.TimedOut) {
    throw "Failed to initialize council bus for $TargetRunDir"
  }
  Log-Line "council bus initialized pattern=$Pattern agents=$AgentCount"
}

<#
.SYNOPSIS
Launch run-agent*.ps1 scripts with bounded parallelism and per-script timeouts.

.DESCRIPTION
Redirects stdout/stderr to per-script log files and enforces MaxRuntimeSec watchdog.
#>
function Start-RunScripts([string]$TargetRunDir, [int]$Parallel, [int]$MaxRuntimeSec) {
  $scripts = Get-ChildItem -LiteralPath $TargetRunDir -File -Filter "run-agent*.ps1" -ErrorAction SilentlyContinue | Sort-Object Name
  if (-not $scripts) {
    Log-Line "no run-agent scripts found in $TargetRunDir (launch skipped)"
    return @()
  }
  if ($Parallel -lt 1) { $Parallel = 1 }

  Log-Line "launching $($scripts.Count) agent scripts (max_parallel=$Parallel)"
  $queue = [System.Collections.Generic.Queue[object]]::new()
  foreach ($s in $scripts) { $queue.Enqueue($s) }
  $active = @()
  $all = @()

  while ($queue.Count -gt 0 -or $active.Count -gt 0) {
    while ($queue.Count -gt 0 -and $active.Count -lt $Parallel) {
      $next = $queue.Dequeue()
      $outLog = Join-Path $TargetRunDir ($next.BaseName + ".stdout.log")
      $errLog = Join-Path $TargetRunDir ($next.BaseName + ".stderr.log")
      $proc = $null

      try {

        $proc = Start-Process -FilePath $script:PowerShellExeResolved -ArgumentList @(

          "-NoProfile",

          "-ExecutionPolicy", "Bypass",

          "-File", $next.FullName

        ) -PassThru -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog

      } catch {

        Log-Line "FAILED to spawn $($next.Name): $($_.Exception.Message)"

        continue

      }

      Log-Line "spawned $($next.Name) pid=$($proc.Id)"
      if ($script:CouncilBusEnabled -and (Test-Path $script:CouncilBusScriptPath)) {
        try {
          & python $script:CouncilBusScriptPath send --run-dir $TargetRunDir --sender orchestrator --receiver council --intent lifecycle --message "spawned $($next.Name) pid=$($proc.Id)" | Out-Null
        } catch {}
      }
      $active += [pscustomobject]@{
        Name = $next.Name
        Process = $proc
        StartedAt = Get-Date
      }
      $all += $active[-1]
    }

    Start-Sleep -Seconds 2
    $still = @()
    foreach ($item in $active) {
      if ($item.Process.HasExited) {
        Log-Line "completed $($item.Name) pid=$($item.Process.Id) exit=$($item.Process.ExitCode)"
        if ($script:CouncilBusEnabled -and (Test-Path $script:CouncilBusScriptPath)) {
          try {
            & python $script:CouncilBusScriptPath send --run-dir $TargetRunDir --sender orchestrator --receiver council --intent lifecycle --message "completed $($item.Name) pid=$($item.Process.Id) exit=$($item.Process.ExitCode)" | Out-Null
          } catch {}
        }
      } else {
        $runtime = (New-TimeSpan -Start $item.StartedAt -End (Get-Date)).TotalSeconds
        if ($runtime -gt $MaxRuntimeSec) {
          try {
            Stop-Process -Id $item.Process.Id -Force
            Log-Line "killed $($item.Name) pid=$($item.Process.Id) reason=timeout runtime_s=$([int]$runtime)"
            if ($script:CouncilBusEnabled -and (Test-Path $script:CouncilBusScriptPath)) {
              try {
                & python $script:CouncilBusScriptPath send --run-dir $TargetRunDir --sender orchestrator --receiver council --intent challenge --message "timeout watchdog kill for $($item.Name) pid=$($item.Process.Id) runtime_s=$([int]$runtime)" | Out-Null
              } catch {}
            }
          } catch {}
        }
        $still += $item
      }
    }
    $active = $still
  }

  return $all
}

try {
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot ".git") -PathType Container)) {
  throw "Not a git repo: $RepoRoot"
}
$queueCircuit = Join-Path $RepoRoot "ramshare\state\queue\circuit_breaker.flag"
if (Test-Path $queueCircuit) {
  throw "Queue circuit breaker is OPEN: $queueCircuit"
}

Assert-GeminiCommand -CommandName 'python'
Assert-GeminiCommand -CommandName 'git'
Wait-GeminiGitLockClear -RepoRoot $RepoRoot -TimeoutSec $GitLockTimeoutSec

$resolvedRunDir = Resolve-RunDir -Base $RepoRoot -Requested $RunDir
$runName = Split-Path $resolvedRunDir -Leaf
$logDir = if (-not [string]::IsNullOrWhiteSpace($LogDirectory)) { $LogDirectory } else { $resolvedRunDir }
Initialize-GeminiLogging -LogDirectory $logDir -LogFileName 'triad_orchestrator.log'
Run-AgentFoundry -BaseRepo $RepoRoot -MissionPrompt $Prompt -TargetRunDir $resolvedRunDir
$script:PowerShellExeResolved = Resolve-PowerShellExe -Requested $PowerShellExe
Write-GeminiLog -Level INFO -Message ("powershell_exe={0}" -f $script:PowerShellExeResolved)

$learningScript = Join-Path $RepoRoot "scripts\agent_self_learning.py"
$efficiencyScript = Join-Path $RepoRoot "scripts\agent_efficiency_learner.py"
$councilLearningScript = Join-Path $RepoRoot "scripts\council_reflection_learner.py"
$capabilityBrokerScript = Join-Path $RepoRoot "scripts\agent_capability_broker.py"
if (-not (Test-Path -LiteralPath $learningScript)) {
  throw "Missing learning script: $learningScript"
}

Push-Location $RepoRoot
try {
  $script:CouncilBusEnabled = $false
  $script:CouncilBusScriptPath = Join-Path $RepoRoot "scripts\council_bus.py"
  $effModel = Load-EfficiencyModel -BaseRepo $RepoRoot
  $learnedFormat = "raw_GEMINI_cmd_exec"
  if ($effModel -and $effModel.preferred_launch_format) {
    $learnedFormat = [string]$effModel.preferred_launch_format
  }
  if ($AutoTuneFromLearning -and $effModel -and $effModel.recommended_agents_per_console) {
    $AgentsPerConsole = [int]$effModel.recommended_agents_per_console
  }
  if (-not $PSBoundParameters.ContainsKey('FailClosedOnThreshold')) {
    $FailClosedOnThreshold = $true
  }
  if (-not $PSBoundParameters.ContainsKey('RequireCouncilDiscussion')) {
    $RequireCouncilDiscussion = $true
  }

  Log-Line "repo=$RepoRoot"
  Log-Line "run_dir=$resolvedRunDir"
  Log-Line "run_id=$runName"
  Log-Line "raw_GEMINI_path=$RawGeminiPath"
  Log-Line "agents_per_console=$AgentsPerConsole"
  Log-Line "launch_format=$learnedFormat"

  $rewrittenCount = Normalize-RunScriptsForRawGemini -TargetRunDir $resolvedRunDir -RawPath $RawGeminiPath -LaunchFormat $learnedFormat
  Log-Line "normalized run scripts for raw Gemini: changed=$rewrittenCount"
  if ($InjectLearningHints) {
    $hintPatch = Inject-PromptLearningHints -BaseRepo $RepoRoot -TargetRunDir $resolvedRunDir
    Log-Line "learning hints injected into prompts: changed=$hintPatch"
  }
  if ($InjectCapabilityContract -or (-not $PSBoundParameters.ContainsKey('InjectCapabilityContract'))) {
    $capPatch = Inject-CapabilityRequestContract -TargetRunDir $resolvedRunDir
    Log-Line "capability request contract injected into prompts: changed=$capPatch"
  }
  if ($EnableCouncilBus) {
    $councilPatch = Inject-CouncilProtocolContract -TargetRunDir $resolvedRunDir -Pattern $CouncilPattern
    Log-Line "council protocol contract injected into prompts: changed=$councilPatch"
    Validate-CouncilManifestContract -TargetRunDir $resolvedRunDir
  }
  
  Inject-MirrorContext -BaseRepo $RepoRoot -TargetRunDir $resolvedRunDir

  $parseFailures = Test-RunScriptParsing -TargetRunDir $resolvedRunDir
  if ($parseFailures.Count -gt 0) {
    throw ("run script parse failures:`n" + ($parseFailures -join "`n"))
  }

  if ($EnableCouncilBus) {
    $agentCount = (Get-ChildItem $resolvedRunDir -File -Filter "run-agent*.ps1" | Measure-Object).Count
    Initialize-CouncilBus -BaseRepo $RepoRoot -TargetRunDir $resolvedRunDir -Pattern $CouncilPattern -AgentCount $agentCount
    $script:CouncilBusEnabled = $true
  }

  if (-not $NoLaunch) {
    # "2 agents per console" maps to effective parallel lanes with desktop-safe cap.
    $requestedParallel = [Math]::Max(1, ($MaxParallel * [Math]::Max(1, $AgentsPerConsole)))
    $safeCap = Get-SafeParallelCap -RequestedCap $MaxEffectiveParallel
    $effectiveParallel = [Math]::Max(1, [Math]::Min($requestedParallel, $safeCap))
    Log-Line "effective_parallel=$effectiveParallel"
        [void](Start-RunScripts -TargetRunDir $resolvedRunDir -Parallel $effectiveParallel -MaxRuntimeSec $MaxAgentRuntimeSeconds)
    
    # --- HUMAN-IN-THE-LOOP GOVERNANCE GATE ---
    $gateScript = Join-Path $PSScriptRoot "governance_gate.py"
    if (Test-Path $gateScript) {
        Write-Host "[Gate] Intercepting for Human Review..." -ForegroundColor Yellow
        $gateProc = Start-Process -FilePath "python" -ArgumentList @($gateScript, $resolvedRunDir) -Wait -NoNewWindow -PassThru
        if ($gateProc.ExitCode -ne 0) {
            Write-Host "[Gate] Plan Vetoed or Gate Error. Stopping/Retrying..." -ForegroundColor Red
            # If vetoed, we might want to loop back or exit. For now, exit 1 to stop the loop.
            exit 1
        }
    }
  } else {
    Log-Line "NoLaunch enabled; skipping agent script execution"
  }

  Log-Line "running close-loop scoring+learning (threshold=$Threshold)"
  $resClose = Invoke-GeminiExternalCommand -FilePath 'python' -ArgumentList @($learningScript, 'close-loop', '--run-dir', $resolvedRunDir, '--threshold', $Threshold) -WorkingDirectory $RepoRoot -TimeoutSec $CloseLoopTimeoutSec
  if ($resClose.ExitCode -ne 0 -or $resClose.TimedOut) {
    throw "close-loop failed for run_dir=$resolvedRunDir"
  }
  $jsonText = ($resClose.StdOut | Out-String).Trim()
  $summaryObj = $null
  try { $summaryObj = $jsonText | ConvertFrom-Json } catch {}
  if ($FailClosedOnThreshold -and -not $summaryObj) {
    throw "Run quality summary parse failed (fail-closed active)"
  }

  $summaryPath = Join-Path $resolvedRunDir "learning-summary.json"
  $jsonText | Set-Content -LiteralPath $summaryPath -Encoding UTF8

  Log-Line "learning summary written: $summaryPath"
  Write-Host $jsonText

  if (Test-Path -LiteralPath $efficiencyScript) {
    Log-Line "updating efficiency model from run outcomes"
    $resEff = Invoke-GeminiExternalCommand -FilePath 'python' -ArgumentList @($efficiencyScript, '--run-dir', $resolvedRunDir) -WorkingDirectory $RepoRoot -TimeoutSec $AuxPythonTimeoutSec
    if ($resEff.ExitCode -eq 0 -and -not $resEff.TimedOut) {
      $effPath = Join-Path $resolvedRunDir "efficiency-summary.json"
      ($resEff.StdOut | Out-String).Trim() | Set-Content -LiteralPath $effPath -Encoding UTF8
      Log-Line "efficiency summary written: $effPath"
    } else {
      Log-Line "efficiency learner failed; continuing without model update"
    }
  }

  $busFile = Join-Path $resolvedRunDir "bus\messages.jsonl"
  if ((Test-Path -LiteralPath $councilLearningScript) -and (Test-Path -LiteralPath $busFile)) {
    Log-Line "learning from council bus discussion"
    $resCouncil = Invoke-GeminiExternalCommand -FilePath 'python' -ArgumentList @($councilLearningScript, '--run-dir', $resolvedRunDir) -WorkingDirectory $RepoRoot -TimeoutSec $AuxPythonTimeoutSec
    if ($resCouncil.ExitCode -eq 0 -and -not $resCouncil.TimedOut) {
      $cPath = Join-Path $resolvedRunDir "council-learning-summary.json"
      $cText = ($resCouncil.StdOut | Out-String).Trim()
      $cText | Set-Content -LiteralPath $cPath -Encoding UTF8
      Log-Line "council learning summary written: $cPath"
      if ($RequireCouncilDiscussion) {
        $cObj = $null
        try { $cObj = $cText | ConvertFrom-Json } catch {}
        if (-not $cObj) {
          throw "Council summary parse failed (require-council-discussion active)"
        }
        if (([int]$cObj.verified -le 0) -or ([int]$cObj.challenged -le 0)) {
          throw "Council protocol not satisfied: verified=$($cObj.verified) challenged=$($cObj.challenged)"
        }
      }
    }
  }
  if (Test-Path $capabilityBrokerScript) {
    Log-Line "resolving capability requests from agent outputs"
    $capArgs = @("--run-dir", $resolvedRunDir)
    if ($AutoApplyMcpCapabilities) { $capArgs += "--auto-apply-mcp" }
    $resCap = Invoke-GeminiExternalCommand -FilePath 'python' -ArgumentList (@($capabilityBrokerScript) + $capArgs) -WorkingDirectory $RepoRoot -TimeoutSec $AuxPythonTimeoutSec
    if ($resCap.ExitCode -eq 0 -and -not $resCap.TimedOut) {
      $capJson = ($resCap.StdOut | Out-String).Trim()
      $capJsonPath = Join-Path $resolvedRunDir "capability-catalog.json"
      $capMdPath = Join-Path $resolvedRunDir "capability-catalog.md"
      if (-not (Test-Path $capJsonPath)) {
        $capJson | Set-Content -LiteralPath $capJsonPath -Encoding UTF8
      }
      Log-Line "capability catalog written: $capMdPath"
      if ($script:CouncilBusEnabled -and (Test-Path $script:CouncilBusScriptPath)) {
        try {
          & python $script:CouncilBusScriptPath send --run-dir $resolvedRunDir --sender orchestrator --receiver council --intent lifecycle --message "capability catalog updated: $(Split-Path $capMdPath -Leaf)" | Out-Null
        } catch {}
      }
    } else {
      Log-Line "capability broker failed; continuing without catalog"
    }
  }
  if ($FailClosedOnThreshold -and $summaryObj -and $summaryObj.avg_score -lt $Threshold) {
    throw "Run quality below threshold: avg_score=$($summaryObj.avg_score) threshold=$Threshold"
  }
} finally {
  Pop-Location
}

}
catch {
  try { Write-GeminiLog -Level ERROR -Message ("fatal: {0}" -f $_.Exception.Message) } catch { }
  try { if ($_.ScriptStackTrace) { Write-GeminiLog -Level DEBUG -Message $_.ScriptStackTrace } } catch { }
  exit 1
}

