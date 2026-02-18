param(
  [ValidateSet('default','dev','browser','research','ops','fidelity','full','screen-readonly','screen-operator','sidecar-operator')]
  [string]$Profile = 'sidecar-operator'
)

$ErrorActionPreference = 'Stop'
$stopped = 0
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pidFile = Join-Path (Join-Path $RepoRoot 'ramshare\state') ("watchdog.{0}.pid" -f $Profile)

$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue
foreach ($p in $procs) {
  $cmd = [string]$p.CommandLine
  if (-not $cmd) { continue }
  if (($cmd -like "*gemini_watchdog.py*") -and ($cmd -like "*--profile $Profile*")) {
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    $stopped += 1
  }
}

Write-Host "Stopped watchdog processes for profile=${Profile}: $stopped"
if (Test-Path $pidFile) {
  Remove-Item -Force $pidFile -ErrorAction SilentlyContinue
}
