param(
  [ValidateSet('restricted','open')]
  [string]$Mode = 'restricted',
  [switch]$RestartGemini
)

$ErrorActionPreference = 'Stop'
$policyPath = 'C:\Gemini\mcp\policy_proxy\policy.json'
$backupDir = 'C:\Gemini\state\policy-backups'
$backupPath = Join-Path $backupDir ('policy.' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')

if (!(Test-Path $policyPath)) {
  throw "Missing policy file: $policyPath"
}

if (!(Test-Path $backupDir)) {
  New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
}

$policy = Get-Content -Raw $policyPath | ConvertFrom-Json
Copy-Item -Force $policyPath $backupPath

switch ($Mode) {
  'open' {
    $policy.filesystem.allow_all_roots = $true
    $policy.network.allow_all_domains = $true
    $policy.network.allow_http = $true
    $policy.shell.allow_all_commands = $true
    # Keep explicit destructive blocklist even in open mode.
  }
  'restricted' {
    $policy.filesystem.allow_all_roots = $false
    $policy.network.allow_all_domains = $false
    $policy.network.allow_http = $false
    $policy.shell.allow_all_commands = $false
  }
}

$policy | ConvertTo-Json -Depth 20 | Set-Content -Path $policyPath -Encoding UTF8
Write-Host "Policy mode set to: $Mode"
Write-Host "Backup written: $backupPath"

if ($RestartGemini) {
  Write-Host "Restarting Gemini-related background processes..."
  Get-CimInstance Win32_Process -Filter "Name='Gemini.exe' OR Name='python.exe' OR Name='powershell.exe'" |
    Where-Object { $_.CommandLine -like '*policy_proxy*' -or $_.CommandLine -like '*Gemini --full-auto*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Write-Host "Restart requested; run start-Gemini.ps1 again for clean session."
}
