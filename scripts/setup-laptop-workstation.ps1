param(
  [string]$ServerHost = 'Gemini-server',
  [string]$ServerAddress = 'REPLACE_WITH_DESKTOP_IP_OR_DNS',
  [string]$ServerUser = 'codym',
  [string]$LocalRepoRoot = '',
  [switch]$SkipScheduledTask
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ServerAddress) -or $ServerAddress -match '^REPLACE_WITH_') {
  throw "ServerAddress must be set to your desktop server IP/DNS (current: '$ServerAddress')."
}

if ([string]::IsNullOrWhiteSpace($LocalRepoRoot)) {
  $LocalRepoRoot = Join-Path $HOME 'Gemini-op'
}

function Ensure-ServiceRunning([string]$Name) {
  $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
  if (-not $svc) { return }
  if ($svc.StartType -ne 'Automatic') { Set-Service -Name $Name -StartupType Automatic }
  if ($svc.Status -ne 'Running') { Start-Service -Name $Name }
}

function Ensure-SshConfigHost {
  param(
    [string]$HostAlias,
    [string]$HostName,
    [string]$UserName
  )
  $sshDir = Join-Path $HOME '.ssh'
  $cfgPath = Join-Path $sshDir 'config'
  if (!(Test-Path $sshDir)) { New-Item -ItemType Directory -Force -Path $sshDir | Out-Null }
  if (!(Test-Path $cfgPath)) { New-Item -ItemType File -Force -Path $cfgPath | Out-Null }
  $content = Get-Content -Raw $cfgPath
  $newBlock = @"
Host $HostAlias
    HostName $HostName
    User $UserName
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
"@
  $pattern = "(?ms)^Host\s+$([regex]::Escape($HostAlias))\s*$.*?(?=^\s*Host\s+|\z)"
  if ($content -match $pattern) {
    $updated = [regex]::Replace($content, $pattern, ($newBlock + [Environment]::NewLine))
    Set-Content -Path $cfgPath -Value $updated -Encoding UTF8
    Write-Host "SSH host entry updated: $HostAlias -> $HostName"
    return
  }
  Add-Content -Path $cfgPath -Value ("`r`n" + $newBlock + "`r`n")
  Write-Host "SSH host entry added: $HostAlias -> $HostName"
}

function Ensure-SshKey {
  $key = Join-Path $HOME '.ssh\id_ed25519'
  if (Test-Path $key) {
    Write-Host "SSH key exists: $key"
    return
  }
  & ssh-keygen -t ed25519 -f $key -N "" | Out-Null
  Write-Host "Created SSH key: $key"
}

Ensure-ServiceRunning -Name 'ssh-agent'
Ensure-SshKey
Ensure-SshConfigHost -HostAlias $ServerHost -HostName $ServerAddress -UserName $ServerUser

$pullScript = Join-Path $PSScriptRoot 'pull-ramshare-from-server.ps1'
$repoRamshare = Join-Path $LocalRepoRoot 'ramshare'
if (!(Test-Path $repoRamshare)) { New-Item -ItemType Directory -Force -Path $repoRamshare | Out-Null }

if (-not $SkipScheduledTask) {
  $taskName = 'GeminiRamsharePull'
  $tr = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$pullScript`" -ServerHost $ServerHost -LocalRamshareRoot `"$repoRamshare`""
  schtasks /Create /TN $taskName /SC MINUTE /MO 5 /TR $tr /F | Out-Null
  Write-Host "Scheduled task configured: $taskName"
}

Write-Host ""
Write-Host "Laptop workstation setup complete."
Write-Host "Desktop server public key should be added to this laptop only if you need reverse SSH."
Write-Host "Next commands:"
Write-Host "1) ssh $ServerHost echo ok"
Write-Host "2) powershell -NoProfile -ExecutionPolicy Bypass -File $pullScript -ServerHost $ServerHost -LocalRamshareRoot `"$repoRamshare`""
