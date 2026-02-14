param(
  [ValidateSet('default','dev','browser','research','full')]
  [string]$Profile = 'research',

  [ValidateSet('prepare','run')]
  [string]$Mode = 'prepare',

  # Optional substring to select only matching task stubs (by filename).
  [string]$Match = '',

  [int]$MaxTasks = 0,

  [switch]$UpdatePlan,

  # If set, auto-promote only lines prefixed with "PROMOTE:" from pending.md into progressive-plan.md.
  [switch]$PromotePlanUpdates
)

$ErrorActionPreference = 'Stop'

$repoRoot = 'C:\Gemini'
$tasksDir = Join-Path $repoRoot 'ramshare\agent-tasks'
$health = Join-Path $repoRoot 'scripts\health.ps1'
$profileScript = Join-Path $repoRoot 'Gemini-profile.ps1'
$planUpdates = Join-Path $repoRoot 'ramshare\plan-updates\pending.md'
$promptsDir = Join-Path $repoRoot 'ramshare\distill-prompts'
$runsDir = Join-Path $repoRoot 'ramshare\distill-runs'
$promoteScript = Join-Path $repoRoot 'scripts\promote-plan-updates.ps1'

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $planUpdates) | Out-Null
New-Item -ItemType Directory -Force -Path $promptsDir | Out-Null
New-Item -ItemType Directory -Force -Path $runsDir | Out-Null

if ($UpdatePlan -and !(Test-Path $planUpdates)) {
  $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
  Set-Content -Path $planUpdates -Value ("# Pending Plan Updates`n`nGenerated: $stamp`n") -NoNewline
}

if (!(Test-Path $tasksDir)) {
  Write-Host "No tasks folder found: $tasksDir"
  exit 0
}

# Preflight (starts daemons for the chosen profile)
if (Test-Path $health) {
  & $health -Profile $Profile -StartDaemons | Out-Null
} else {
  Write-Host "WARN: missing health script: $health"
}

$shouldApplyProfile = ($Mode -eq 'run')
if ($shouldApplyProfile) {
  # Apply profile by copying repo profile -> C:\Gemini\config.toml.
  if (Test-Path $profileScript) {
    & $profileScript -Profile $Profile | Out-Null
  } else {
    Write-Host "WARN: missing profile script: $profileScript"
  }
}

$taskFiles = Get-ChildItem -Path $tasksDir -File -Filter *.md -ErrorAction SilentlyContinue | Sort-Object Name
if ($Match) {
  $taskFiles = $taskFiles | Where-Object { $_.Name -like ("*{0}*" -f $Match) }
}
if ($MaxTasks -gt 0) {
  $taskFiles = $taskFiles | Select-Object -First $MaxTasks
}

if (-not $taskFiles) {
  Write-Host "No pending distill tasks in $tasksDir"
  exit 0
}

function Get-FirstBacktickPath([string]$line) {
  $m = [regex]::Match($line, '`([^`]+)`')
  if ($m.Success) { return $m.Groups[1].Value }
  return $null
}

function Write-PromptFile(
  [string]$taskPath,
  [string]$sourcePath,
  [string]$outPath,
  [string]$promptPath
) {
  $lines = New-Object System.Collections.Generic.List[string]
  $lines.Add('You are working inside the Gemini-op repo at `C:\\Gemini`.') | Out-Null
  $lines.Add("") | Out-Null
  $lines.Add("Goal: distill the source document into a short, actionable note for this project (Gemini-op).") | Out-Null
  $lines.Add("") | Out-Null
  $lines.Add("Inputs:") | Out-Null
  $lines.Add(('- Task stub: `{0}`' -f $taskPath)) | Out-Null
  $lines.Add(('- Raw extracted text: `{0}`' -f $sourcePath)) | Out-Null
  $lines.Add("") | Out-Null
  $lines.Add("Output:") | Out-Null
  $lines.Add(('- Write the distilled note to: `{0}`' -f $outPath)) | Out-Null
  $lines.Add("") | Out-Null
  $lines.Add("Distilled note format (keep it tight):") | Out-Null
  $lines.Add("# <Title>") | Out-Null
  $lines.Add("") | Out-Null
  $lines.Add("## Summary") | Out-Null
  $lines.Add("- Max 10 bullets.") | Out-Null
  $lines.Add("") | Out-Null
  $lines.Add("## Gemini-op Implications (prioritized)") | Out-Null
  $lines.Add("- P0: things to change now (concrete files/commands)") | Out-Null
  $lines.Add("- P1: next improvements") | Out-Null
  $lines.Add("- P2: later / nice-to-have") | Out-Null
  $lines.Add("") | Out-Null
  $lines.Add("## Mapping to This Repo") | Out-Null
  $lines.Add('- profiles: `profiles/config.*.toml`') | Out-Null
  $lines.Add('- daemons: `start-daemons.ps1` and `mcp-daemons/`') | Out-Null
  $lines.Add('- ingestion: `scripts/ingest-and-index.ps1`') | Out-Null
  $lines.Add('- notes: `ramshare/notes/`') | Out-Null
  $lines.Add("") | Out-Null
  $lines.Add("## Commands / Config Snippets") | Out-Null
  $lines.Add("- Only include commands/snippets that are actually applicable here.") | Out-Null
  $lines.Add("") | Out-Null
  $lines.Add("## Risks / Gotchas") | Out-Null
  $lines.Add("- Short bullets.") | Out-Null
  $lines.Add("") | Out-Null
  $lines.Add("## Tags") | Out-Null
  $lines.Add('- e.g. `security`, `governance`, `ml`, `indexing`, `mcp`, `sandbox`') | Out-Null
  $lines.Add("") | Out-Null
  $lines.Add("Rules:") | Out-Null
  $lines.Add("- Prefer actionable + repo-specific guidance over generic textbook summary.") | Out-Null
  $lines.Add("- If the raw extract is huge/noisy, use semantic-search to locate relevant passages.") | Out-Null
  if ($UpdatePlan) {
    $lines.Add("- Also append net-new repo decisions (only concrete actions) to this file:") | Out-Null
    $lines.Add(('  - `{0}`' -f $planUpdates)) | Out-Null
    $lines.Add("- Prefix any line that is safe to auto-merge with `PROMOTE:`. (Unsafe/uncertain notes should NOT use the prefix.)") | Out-Null
  }

  Set-Content -Path $promptPath -Value ($lines -join "`n") -NoNewline
}

$prepared = 0
foreach ($t in $taskFiles) {
  $content = Get-Content -Path $t.FullName -Raw -ErrorAction Stop
  $sourceLine = ($content -split "`n") | Where-Object { $_ -match '^Source:' } | Select-Object -First 1
  $outLine = ($content -split "`n") | Where-Object { $_ -match '^- Write distilled note to:' } | Select-Object -First 1

  $sourcePath = if ($sourceLine) { Get-FirstBacktickPath $sourceLine } else { $null }
  $outPath = if ($outLine) { Get-FirstBacktickPath $outLine } else { $null }

  if (-not $sourcePath -or -not (Test-Path $sourcePath)) {
    Write-Host "SKIP: can't find source for task: $($t.Name)"
    continue
  }
  if (-not $outPath) {
    Write-Host "SKIP: can't find output path for task: $($t.Name)"
    continue
  }

  $promptPath = Join-Path $promptsDir ($t.BaseName + '.prompt.txt')
  Write-PromptFile -taskPath $t.FullName -sourcePath $sourcePath -outPath $outPath -promptPath $promptPath
  $prepared++

  if ($Mode -eq 'run') {
    # Ensure Gemini uses this repo config.
    $env:GEMINI_CONFIG = Join-Path $repoRoot 'config.toml'

    Write-Host "RUN: distilling $($t.Name)"
    $lastMsg = Join-Path $runsDir ($t.BaseName + '.last.md')

    # Prompt from stdin: Gemini exec - < prompt
    Get-Content -Path $promptPath -Raw | Gemini exec - --full-auto -C $repoRoot --output-last-message $lastMsg

    if (Test-Path $lastMsg) {
      $txt = Get-Content -Path $lastMsg -Raw -ErrorAction SilentlyContinue
      if ($txt -and $txt.Trim().Length -gt 0) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outPath) | Out-Null
        Set-Content -Path $outPath -Value $txt -NoNewline
        Write-Host "WROTE: $outPath"

        if ($UpdatePlan -and $PromotePlanUpdates -and (Test-Path $promoteScript)) {
          try {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $promoteScript | Out-Null
          } catch {
            Write-Host "WARN: plan auto-promote failed: $($_.Exception.Message)"
          }
        }
      } else {
        Write-Host "WARN: empty output from Gemini exec: $lastMsg"
      }
    } else {
      Write-Host "WARN: missing Gemini exec output file: $lastMsg"
    }
  }
}

Write-Host ""
Write-Host "Prepared $prepared prompt(s) in: $promptsDir"
if ($UpdatePlan) {
  Write-Host ("Plan updates (pending): {0}" -f $planUpdates)
}
