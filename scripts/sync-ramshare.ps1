param(
  [string]$ConfigPath = 'C:\Gemini\scripts\ramshare-sync.local.json',
  [switch]$AllowLocalhostTarget,
  [int]$StaleLockMinutes = 15
)

$ErrorActionPreference = 'Stop'
$lockPath = 'C:\Gemini\state\locks\ramshare-sync.lock'

function Log-Info([string]$Message) {
  $log = 'C:\Gemini\logs\sync\ramshare-sync.log'
  $line = "[$(Get-Date -Format o)] $Message"
  $dir = Split-Path -Parent $log
  if (!(Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Add-Content -Path $log -Value $line
  Write-Host $line
}

if (!(Test-Path $ConfigPath)) {
  Log-Info "Missing config: $ConfigPath"
  exit 1
}

$lockDir = Split-Path -Parent $lockPath
if (!(Test-Path $lockDir)) { New-Item -ItemType Directory -Force -Path $lockDir | Out-Null }
if (Test-Path $lockPath) {
  $lockText = ''
  try { $lockText = Get-Content -Raw $lockPath } catch {}
  $lockPid = $null
  $lockStart = $null
  if ($lockText -match 'pid=(\d+);\s*started=([^\r\n]+)') {
    $lockPid = [int]$matches[1]
    try { $lockStart = [datetime]::Parse($matches[2]) } catch {}
  }

  $isActive = $false
  if ($lockPid) {
    $p = Get-Process -Id $lockPid -ErrorAction SilentlyContinue
    if ($p) { $isActive = $true }
  }

  $isStaleByAge = $false
  if ($lockStart) {
    $isStaleByAge = ((Get-Date) - $lockStart).TotalMinutes -ge $StaleLockMinutes
  }

  if ($isActive -and -not $isStaleByAge) {
    Log-Info "Skip: another sync run is already in progress (lock present)."
    exit 0
  }

  Log-Info "Removing stale lock and continuing."
  Remove-Item -Force $lockPath -ErrorAction SilentlyContinue
}
Set-Content -Path $lockPath -Value ("pid={0}; started={1}" -f $PID, (Get-Date -Format o)) -Encoding UTF8

try {
  $cfg = Get-Content -Raw $ConfigPath | ConvertFrom-Json
  if (-not $cfg.enabled) {
    Log-Info "ramshare sync disabled in config"
    exit 0
  }

$sshHost = [string]$cfg.ssh_host
$remoteRoot = [string]$cfg.remote_ramshare_root
$localRoot = [string]$cfg.local_ramshare_root
$paths = @($cfg.include_paths)
if (-not $paths -or $paths.Count -eq 0) {
  Log-Info "No include_paths configured"
  exit 0
}

  if (!(Test-Path $localRoot)) {
    Log-Info "Local root missing: $localRoot"
    exit 1
  }

  if ([string]::IsNullOrWhiteSpace($sshHost) -or $sshHost -match 'REPLACE_WITH_') {
    Log-Info "Invalid ssh_host in config ($ConfigPath). Set ssh_host to your laptop alias or DNS name."
    exit 1
  }

$sshOpts = @(
  '-o', 'BatchMode=yes',
  '-o', 'ConnectTimeout=8',
  '-o', 'ConnectionAttempts=1',
  '-o', 'ServerAliveInterval=5',
  '-o', 'ServerAliveCountMax=1'
)

# Safety check: prevent accidental sync-to-self unless explicitly allowed
  try {
    $remoteHost = (& ssh @sshOpts $sshHost hostname 2>$null | Select-Object -First 1).Trim().ToUpperInvariant()
  } catch {
    $remoteHost = ''
  }
  $localHost = $env:COMPUTERNAME.ToUpperInvariant()
  if (-not $AllowLocalhostTarget -and $remoteHost -and $remoteHost -eq $localHost) {
    Log-Info ("Refusing sync: ssh_host '{0}' resolves to local host ({1}). Fix ~/.ssh/config HostName for this alias." -f $sshHost, $localHost)
    exit 1
  }

# Ensure remote root exists (Linux shell first, then Windows PowerShell shell)
$mkdirOk = $false
$linuxMkdirCmd = "mkdir -p '$remoteRoot'"
$linuxOut = $null
try {
  $linuxOut = & ssh @sshOpts $sshHost $linuxMkdirCmd 2>&1
  if ($LASTEXITCODE -eq 0) { $mkdirOk = $true }
} catch {
  $linuxOut = $_.Exception.Message
}

  if (-not $mkdirOk) {
  $remoteRootWin = $remoteRoot
  if ($remoteRootWin.StartsWith('~/')) {
    $tail = $remoteRootWin.Substring(2).Replace('/', '\')
    $remoteRootWin = "%USERPROFILE%\$tail"
  } else {
    $remoteRootWin = $remoteRootWin.Replace('/', '\')
  }
  $winMkdirCmd = "cmd /c if not exist `"$remoteRootWin`" mkdir `"$remoteRootWin`""
  $winOut = $null
  try {
    $winOut = & ssh @sshOpts $sshHost $winMkdirCmd 2>&1
    if ($LASTEXITCODE -eq 0) { $mkdirOk = $true }
  } catch {
    $winOut = $_.Exception.Message
  }
  if (-not $mkdirOk) {
    Log-Info ('Remote mkdir failed on {0}. linux_out={1} windows_out={2}' -f $sshHost, ($linuxOut -join ' '), ($winOut -join ' '))
    exit 1
  }
  }

  foreach ($rel in $paths) {
  $relPath = [string]$rel
  $src = Join-Path $localRoot $relPath
  if (!(Test-Path $src)) {
    Log-Info "Skip missing path: $src"
    continue
  }
  $dst = ('{0}:{1}/' -f $sshHost, $remoteRoot)
  Log-Info ('Syncing {0} -> {1}:{2}/' -f $src, $sshHost, $remoteRoot)
  try {
    & scp @sshOpts -r $src $dst 2>&1 | Out-Null
  } catch {
    Log-Info ('SCP threw for {0}: {1}' -f $src, $_.Exception.Message)
    exit 1
  }
  if ($LASTEXITCODE -ne 0) {
  Log-Info "SCP failed for $src"
    exit 1
  }
  }

  Log-Info "ramshare sync complete"
  exit 0
}
finally {
  if (Test-Path $lockPath) {
    Remove-Item -Force $lockPath -ErrorAction SilentlyContinue
  }
}
