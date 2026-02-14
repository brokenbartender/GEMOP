$ErrorActionPreference = 'SilentlyContinue'

function Stop-ListeningPort([int]$Port, [string]$Name) {
  $attempts = 0
  while ($attempts -lt 5) {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $c) {
      if ($attempts -eq 0) {
        Write-Host " -> $Name not listening on :$Port"
      } else {
        Write-Host " -> $Name stopped on :$Port"
      }
      return
    }
    $pid = $c.OwningProcess
    Write-Host " -> stopping $Name on :$Port (PID $pid)"
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 250
    $attempts++
  }
  Write-Host " -> $Name still listening on :$Port after retries (manual cleanup may be needed)"
}

Write-Host "Stopping MCP daemons..."
Stop-ListeningPort -Port 3013 -Name 'memory'
Stop-ListeningPort -Port 8931 -Name 'playwright'
Stop-ListeningPort -Port 3014 -Name 'semantic-search'
