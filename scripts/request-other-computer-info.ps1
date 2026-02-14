param(
  [string]$TargetLabel = 'laptop',
  [string]$RepoPathHint = 'C:\Users\codym\Gemini-op'
)

$ErrorActionPreference = 'Stop'

Write-Host "Collect and send this from your $TargetLabel:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1) Machine identity + network"
Write-Host "   hostname"
Write-Host "   ipconfig | findstr /R /C:`"IPv4`""
Write-Host ""
Write-Host "2) SSH service status"
Write-Host "   Get-Service sshd | Select-Object Name,Status,StartType"
Write-Host "   Test-NetConnection -ComputerName localhost -Port 22 | Select-Object TcpTestSucceeded"
Write-Host ""
Write-Host "3) Repo path + branch"
Write-Host ("   Test-Path `"{0}`"; if (Test-Path `"{0}`") {{ git -C `"{0}`" status --short --branch }}" -f $RepoPathHint)
Write-Host ""
Write-Host "4) If a step fails, send exact error text."
