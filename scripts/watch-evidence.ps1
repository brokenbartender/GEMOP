param(
  [ValidateSet('default','dev','browser','research','full')]
  [string]$Profile = 'research',

  [int]$DebounceSeconds = 5,

  # After ingest completes, automatically run distillation for new evidence tasks.
  [switch]$AutoDistill,

  # If AutoDistill, append plan suggestions and auto-promote only PROMOTE: lines.
  [switch]$AutoPromotePlan
)

$ErrorActionPreference = 'Stop'

$repoRoot = 'C:\Gemini'
$inbox = Join-Path $repoRoot 'ramshare\evidence\inbox'
$ingest = Join-Path $repoRoot 'scripts\ingest-and-index.ps1'
$distill = Join-Path $repoRoot 'scripts\distill.ps1'

New-Item -ItemType Directory -Force -Path $inbox | Out-Null

Write-Host "Watching evidence inbox: $inbox"
Write-Host "Profile: $Profile"
Write-Host "Debounce: $DebounceSeconds seconds"
Write-Host ""
Write-Host "Drop files into the inbox; ingestion will run after changes settle."
Write-Host "Stop with Ctrl+C."

$script:pending = $false
$script:lastEventAt = Get-Date
$script:running = $false

function Mark-Pending {
  $script:pending = $true
  $script:lastEventAt = Get-Date
}

function Try-RunIngest {
  if (-not $script:pending) { return }
  if ($script:running) { return }

  $age = (New-TimeSpan -Start $script:lastEventAt -End (Get-Date)).TotalSeconds
  if ($age -lt $DebounceSeconds) { return }

  $script:pending = $false
  $script:running = $true
  try {
    $stamp = (Get-Date -Format o)
    Write-Host "[$stamp] running ingest-and-index.ps1 (profile=$Profile)"
    # Evidence drops should be fast; do not refresh the whole resources catalog.
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ingest -Profile $Profile -SkipRefreshResources -SkipSemanticReindex
    Write-Host "[$(Get-Date -Format o)] ingest complete"

    if ($AutoDistill -and (Test-Path $distill)) {
      $stamp = (Get-Date -Format o)
      Write-Host "[$stamp] running distill.ps1 for evidence tasks"

      $args = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $distill,
        '-Profile', $Profile,
        '-Mode', 'run',
        '-Match', 'ramshare_evidence_inbox_',
        '-UpdatePlan'
      )
      if ($AutoPromotePlan) {
        $args += '-PromotePlanUpdates'
      }

      & powershell.exe @args
      Write-Host "[$(Get-Date -Format o)] distill complete"
    }
  } catch {
    Write-Host "WARN: ingest failed: $($_.Exception.Message)"
  } finally {
    $script:running = $false
  }
}

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $inbox
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true
$watcher.NotifyFilter = [IO.NotifyFilters]'FileName, DirectoryName, LastWrite, Size'

Register-ObjectEvent -InputObject $watcher -EventName Created -Action { Mark-Pending } | Out-Null
Register-ObjectEvent -InputObject $watcher -EventName Changed -Action { Mark-Pending } | Out-Null
Register-ObjectEvent -InputObject $watcher -EventName Renamed -Action { Mark-Pending } | Out-Null

$timer = New-Object System.Timers.Timer
$timer.Interval = 1000
$timer.AutoReset = $true
Register-ObjectEvent -InputObject $timer -EventName Elapsed -Action { Try-RunIngest } | Out-Null
$timer.Start()

while ($true) {
  Wait-Event -Timeout 1 | Out-Null
}
