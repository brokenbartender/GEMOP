param(
  [string]$LaptopHost = 'Gemini-laptop',
  [string]$LaptopAddress = 'REPLACE_WITH_LAPTOP_IP_OR_DNS',
  [string]$LaptopUser = 'codym',
  [string]$RemoteRepoRoot = '~/Gemini-op',
  [switch]$SkipScheduledTask,
  [switch]$AllowLocalhostTarget
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($LaptopAddress) -or $LaptopAddress -match '^REPLACE_WITH_') {
  throw "LaptopAddress must be set to a real IP or DNS (current: '$LaptopAddress')."
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
Ensure-ServiceRunning -Name 'sshd'

Ensure-SshKey
Ensure-SshConfigHost -HostAlias $LaptopHost -HostName $LaptopAddress -UserName $LaptopUser

try {
  $remoteHost = (& ssh $LaptopHost hostname 2>$null | Select-Object -First 1).Trim().ToUpperInvariant()
} catch {
  $remoteHost = ''
}
$localHost = $env:COMPUTERNAME.ToUpperInvariant()
if (-not $AllowLocalhostTarget -and $remoteHost -and $remoteHost -eq $localHost) {
  throw "Refusing configuration: '$LaptopHost' resolves to local host ($localHost). Set LaptopAddress to the real laptop IP/DNS."
}

$localCfg = 'C:\Gemini\scripts\ramshare-sync.local.json'
if (!(Test-Path $localCfg)) {
  $sample = Get-Content -Raw 'C:\Gemini\scripts\ramshare-sync.sample.json' | ConvertFrom-Json
  $sample.ssh_host = $LaptopHost
  $sample.remote_ramshare_root = "$RemoteRepoRoot/ramshare"
  $sample | ConvertTo-Json -Depth 8 | Set-Content -Path $localCfg -Encoding UTF8
  Write-Host "Created local sync config: $localCfg"
}

if (-not $SkipScheduledTask) {
  $taskName = 'GeminiRamshareSync'
  $script = 'C:\Gemini\scripts\sync-ramshare.ps1'
  $tr = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$script`""
  schtasks /Create /TN $taskName /SC MINUTE /MO 5 /TR $tr /F | Out-Null
  Write-Host "Scheduled task configured: $taskName"
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "1) Copy public key to laptop authorized_keys:"
Write-Host "   type $HOME\\.ssh\\id_ed25519.pub"
Write-Host "2) On laptop, add key to ~/.ssh/authorized_keys and ensure sshd is running."
Write-Host "3) Test:"
Write-Host "   ssh $LaptopHost echo ok"
Write-Host "4) Run one sync manually:"
Write-Host "   powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Gemini\\scripts\\sync-ramshare.ps1"
