$ErrorActionPreference = 'SilentlyContinue'
$CurrentPID = $PID # Get the Commander's session ID

function Stop-ListeningPort([int]$Port, [string]$Name) {
  $attempts = 0
  while ($attempts -lt 5) {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $c) {
      Write-Host " -> $Name not listening on :$Port"
      return
    }
    $targetPid = $c.OwningProcess
    
    # SURVIVOR CHECK: Don't kill yourself
    if ($targetPid -eq $CurrentPID) {
        Write-Host " -> [SAFE] Skipping self-termination on :$Port (PID $targetPid)" -ForegroundColor Green
        return
    }

    Write-Host " -> stopping $Name on :$Port (PID $targetPid)"
    Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 250
    $attempts++
  }
}

Write-Host "Stopping MCP daemons with Survivor Protocol..."
Stop-ListeningPort -Port 3013 -Name 'memory'
Stop-ListeningPort -Port 8931 -Name 'playwright'
Stop-ListeningPort -Port 3014 -Name 'semantic-search'
