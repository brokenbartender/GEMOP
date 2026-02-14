[CmdletBinding(SupportsShouldProcess=$true)]
param(
  [string]$WorkerUser = 'GeminiWorker',
  [SecureString]$WorkerPassword,
  [string]$LoopbackHost = '127.0.0.1'
)

$ErrorActionPreference = 'Stop'

function Test-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($id)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Ensure-LocalUser {
  param([string]$UserName, [SecureString]$Password)
  $existing = Get-LocalUser -Name $UserName -ErrorAction SilentlyContinue
  if ($existing) {
    Write-Host "User exists: $UserName"
    return
  }
  if (-not $Password) {
    if ($WhatIfPreference) {
      $Password = ConvertTo-SecureString 'WhatIf-Only-Password-123!' -AsPlainText -Force
    } else {
      $Password = Read-Host -AsSecureString "Enter password for local user '$UserName'"
    }
  }
  if ($PSCmdlet.ShouldProcess("local user $UserName", "create")) {
    New-LocalUser -Name $UserName -Password $Password -AccountNeverExpires -PasswordNeverExpires | Out-Null
  }
}

function Ensure-GroupMember {
  param([string]$GroupName, [string]$MemberName)
  try {
    $member = Get-LocalGroupMember -Group $GroupName -ErrorAction Stop | Where-Object { $_.Name -like "*\$MemberName" }
    if ($member) {
      Write-Host "$MemberName is already in $GroupName"
      return
    }
    if ($PSCmdlet.ShouldProcess("$GroupName", "add $MemberName")) {
      Add-LocalGroupMember -Group $GroupName -Member $MemberName -ErrorAction Stop
    }
  } catch {
    Write-Warning "Could not update group '$GroupName': $($_.Exception.Message)"
  }
}

if (-not (Test-Admin)) {
  if ($WhatIfPreference) {
    Write-Warning "setup-sidecar.ps1 should run as Administrator. Continuing because -WhatIf is set."
  } else {
    throw "setup-sidecar.ps1 must run as Administrator."
  }
}

Write-Host "Configuring sidecar environment..."

Ensure-LocalUser -UserName $WorkerUser -Password $WorkerPassword
Ensure-GroupMember -GroupName 'Remote Desktop Users' -MemberName $WorkerUser

if ($PSCmdlet.ShouldProcess("Terminal Services", "enable RDP")) {
  Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -Name 'fDenyTSConnections' -Value 0
  Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -Name 'fSingleSessionPerUser' -Value 0
  Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -Name 'UserAuthentication' -Value 1
}

if ($PSCmdlet.ShouldProcess("Firewall", "enable Remote Desktop rule group")) {
  Enable-NetFirewallRule -DisplayGroup 'Remote Desktop' | Out-Null
}

$sidecarDir = 'C:\Gemini\sidecar'
if (!(Test-Path $sidecarDir)) {
  if ($PSCmdlet.ShouldProcess($sidecarDir, "create directory")) {
    New-Item -Path $sidecarDir -ItemType Directory -Force | Out-Null
  }
}

$stateDir = 'C:\Gemini\ramshare\state\sidecar'
if (!(Test-Path $stateDir)) {
  if ($PSCmdlet.ShouldProcess($stateDir, "create directory")) {
    New-Item -Path $stateDir -ItemType Directory -Force | Out-Null
  }
}

$configPath = Join-Path $sidecarDir 'sidecar-config.json'
$config = [ordered]@{
  worker_user = $WorkerUser
  host = $LoopbackHost
  sidecar_window_patterns = @(
    'remote desktop',
    'mstsc',
    'vmconnect'
  )
  workspace = 'C:\Gemini\work'
  sidecar_state_dir = $stateDir
}

if ($PSCmdlet.ShouldProcess($configPath, "write sidecar config")) {
  $config | ConvertTo-Json -Depth 6 | Set-Content -Path $configPath -Encoding UTF8
}

Write-Host "Sidecar setup complete."
Write-Host "Config: $configPath"
Write-Host "Next: run scripts\\start-sidecar.ps1"
