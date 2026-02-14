param(
  [string]$ServerHost = 'Gemini-server',
  [string]$ServerRamshareRoot = '/C:/Gemini/ramshare',
  [string]$LocalRamshareRoot = '',
  [string[]]$IncludePaths = @('state', 'strategy', 'evidence'),
  [switch]$AllowLocalhostTarget
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($LocalRamshareRoot)) {
  $LocalRamshareRoot = Join-Path $HOME 'Gemini-op\ramshare'
}

function Write-Log([string]$Message) {
  $log = Join-Path $HOME 'Gemini-op\logs\ramshare-pull.log'
  $line = "[$(Get-Date -Format o)] $Message"
  $dir = Split-Path -Parent $log
  if (!(Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Add-Content -Path $log -Value $line
  Write-Host $line
}

$sshOpts = @(
  '-o', 'BatchMode=yes',
  '-o', 'ConnectTimeout=8',
  '-o', 'ConnectionAttempts=1',
  '-o', 'ServerAliveInterval=5',
  '-o', 'ServerAliveCountMax=1'
)

if (!(Test-Path $LocalRamshareRoot)) {
  New-Item -ItemType Directory -Force -Path $LocalRamshareRoot | Out-Null
}

try {
  $remoteHost = (& ssh @sshOpts $ServerHost hostname 2>$null | Select-Object -First 1).Trim().ToUpperInvariant()
} catch {
  Write-Log ("Failed to query remote host '{0}': {1}" -f $ServerHost, $_.Exception.Message)
  exit 1
}
$localHost = $env:COMPUTERNAME.ToUpperInvariant()
if (-not $AllowLocalhostTarget -and $remoteHost -and $remoteHost -eq $localHost) {
  Write-Log ("Refusing pull: ServerHost '{0}' resolves to local host ({1})." -f $ServerHost, $localHost)
  exit 1
}

foreach ($rel in $IncludePaths) {
  $src = "{0}:{1}/{2}" -f $ServerHost, $ServerRamshareRoot.TrimEnd('/'), $rel
  $dst = "{0}\" -f $LocalRamshareRoot.TrimEnd('\')
  Write-Log ("Pulling {0} -> {1}" -f $src, $dst)
  try {
    & scp @sshOpts -r $src $dst 2>&1 | Out-Null
  } catch {
    Write-Log ("SCP threw for {0}: {1}" -f $rel, $_.Exception.Message)
    exit 1
  }
  if ($LASTEXITCODE -ne 0) {
    Write-Log ("SCP failed for {0}" -f $rel)
    exit 1
  }
}

Write-Log "ramshare pull complete"
exit 0
