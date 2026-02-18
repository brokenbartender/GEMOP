param(
  [ValidateSet('default','dev','browser','research','ops','fidelity','full','screen-readonly','screen-operator','sidecar-operator')]
  [string]$Profile = 'sidecar-operator',
  [int]$IntervalSeconds = 20,
  [int]$FailureThreshold = 2,
  [int]$RestartCooldownSeconds = 45,
  [switch]$AutoRestartSidecar
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$py = 'python'
$script = (Join-Path $RepoRoot 'scripts\gemini_watchdog.py')
$logDir = (Join-Path $RepoRoot 'logs')
$stateDir = (Join-Path $RepoRoot 'ramshare\state')
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
if (!(Test-Path $stateDir)) { New-Item -ItemType Directory -Force -Path $stateDir | Out-Null }
$pidFile = Join-Path $stateDir ("watchdog.{0}.pid" -f $Profile)

if (Test-Path $pidFile) {
  try {
    $existingPid = [int](Get-Content -Raw $pidFile).Trim()
    $existing = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
    if ($existing) {
      Write-Host "Watchdog already running for profile=$Profile (pid=$existingPid via pidfile)"
      exit 0
    }
  } catch {
    # stale/invalid pid file: continue and overwrite below
  }
}

$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue
foreach ($p in $procs) {
  $cmd = [string]$p.CommandLine
  if ($cmd -and ($cmd -like "*gemini_watchdog.py*") -and ($cmd -like "*--profile $Profile*")) {
    Set-Content -Path $pidFile -Value $p.ProcessId -Encoding ASCII
    Write-Host "Watchdog already running for profile=$Profile (pid=$($p.ProcessId))"
    exit 0
  }
}

$args = @(
  '-u',
  $script,
  '--profile', $Profile,
  '--interval-seconds', "$IntervalSeconds",
  '--failure-threshold', "$FailureThreshold",
  '--restart-cooldown-seconds', "$RestartCooldownSeconds"
)
if ($AutoRestartSidecar) { $args += '--auto-restart-sidecar' }

$outLog = Join-Path $logDir "watchdog.$Profile.out.log"
$errLog = Join-Path $logDir "watchdog.$Profile.err.log"

$proc = Start-Process -FilePath $py -ArgumentList $args -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
Set-Content -Path $pidFile -Value $proc.Id -Encoding ASCII
Write-Host "Started watchdog for profile=$Profile (pid=$($proc.Id))"
