[CmdletBinding(SupportsShouldProcess=$true)]
param(
  [string]$ConfigPath = 'C:\Gemini\sidecar\sidecar-config.json',
  [switch]$ClearCredentials
)

$ErrorActionPreference = 'Stop'

$hostTarget = '127.0.0.1'
$sidecarDir = 'C:\Gemini\sidecar'
if (Test-Path $ConfigPath) {
  try {
    $cfg = Get-Content -Raw $ConfigPath | ConvertFrom-Json
    if ($cfg.host) { $hostTarget = [string]$cfg.host }
    $sidecarDir = Split-Path -Parent $ConfigPath
  } catch {
    Write-Warning "Could not parse config; using defaults."
  }
}

$rdpPath = Join-Path $sidecarDir 'sidecar.rdp'
$killed = 0

$procs = Get-CimInstance Win32_Process -Filter "Name='mstsc.exe'" -ErrorAction SilentlyContinue
foreach ($p in $procs) {
  $cmd = [string]$p.CommandLine
  if ($cmd -and $cmd.ToLower().Contains($rdpPath.ToLower())) {
    if ($PSCmdlet.ShouldProcess("mstsc pid=$($p.ProcessId)", "terminate sidecar session")) {
      Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
      $killed += 1
    }
  }
}

if ($ClearCredentials) {
  if ($PSCmdlet.ShouldProcess("Credential Manager", "remove TERMSRV/$hostTarget")) {
    & cmdkey.exe /delete:"TERMSRV/$hostTarget" | Out-Null
  }
}

Write-Host "Stopped sidecar sessions: $killed"
