[CmdletBinding(SupportsShouldProcess=$true)]
param(
  [string]$ConfigPath = 'C:\Gemini\sidecar\sidecar-config.json',
  [string]$Password,
  [switch]$NoStoreCredentials
)

$ErrorActionPreference = 'Stop'

if (!(Test-Path $ConfigPath)) {
  if ($WhatIfPreference) {
    Write-Warning "Missing sidecar config: $ConfigPath. Run scripts\setup-sidecar.ps1 first."
    return
  }
  throw "Missing sidecar config: $ConfigPath. Run scripts\setup-sidecar.ps1 first."
}

$cfg = Get-Content -Raw $ConfigPath | ConvertFrom-Json
$hostTarget = if ($cfg.host) { [string]$cfg.host } else { '127.0.0.1' }
$user = [string]$cfg.worker_user
if (-not $user) { throw "sidecar-config missing worker_user." }

$sidecarDir = Split-Path -Parent $ConfigPath
$rdpPath = Join-Path $sidecarDir 'sidecar.rdp'

$rdpText = @"
screen mode id:i:2
use multimon:i:0
desktopwidth:i:1920
desktopheight:i:1080
session bpp:i:32
full address:s:$hostTarget
prompt for credentials:i:0
administrative session:i:0
redirectclipboard:i:1
redirectprinters:i:0
redirectcomports:i:0
redirectsmartcards:i:0
drivestoredirect:s:
username:s:$user
"@

if ($PSCmdlet.ShouldProcess($rdpPath, "write RDP launch profile")) {
  $rdpText | Set-Content -Path $rdpPath -Encoding ASCII
}

if (-not $NoStoreCredentials) {
  if (-not $Password) { $Password = $env:GEMINI_SIDECAR_PASSWORD }
  if (-not $Password) {
    $secure = Read-Host -AsSecureString "Enter password for $user"
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $Password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
  }
  if (-not $Password) { throw "No password supplied." }
  if ($PSCmdlet.ShouldProcess("Credential Manager", "store TERMSRV/$hostTarget for $user")) {
    & cmdkey.exe /generic:"TERMSRV/$hostTarget" /user:$user /pass:$Password | Out-Null
  }
}

if ($PSCmdlet.ShouldProcess("mstsc", "start sidecar session")) {
  Start-Process -FilePath 'mstsc.exe' -ArgumentList @($rdpPath) | Out-Null
}

Write-Host "Sidecar launch requested."
Write-Host "RDP profile: $rdpPath"
