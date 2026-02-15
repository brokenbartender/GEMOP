# Gemini-OP Nuclear Reset Protocol
Write-Host "⚠️ INITIATING NUCLEAR RESET..." -ForegroundColor Red

# 1. Stop all agentic processes
$targets = @("python", "node", "gemini", "pwsh")
foreach ($t in $targets) {
    Get-Process -Name $t -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*gemini-op-clean*" -and $_.Id -ne $PID } | Stop-Process -Force -ErrorAction SilentlyContinue
}

# 2. Clear stop flags
$REPO_ROOT = "C:\Users\codym\gemini-op-clean"
Remove-Item "$REPO_ROOT\STOP_ALL_AGENTS.flag" -Force -ErrorAction SilentlyContinue

# 3. Restart core daemons
Write-Host "Restarting Heartbeat and Deputy..." -ForegroundColor Green
Start-Process "python" -ArgumentList "$REPO_ROOT\scripts\gemini_heartbeat.py" -WorkingDirectory $REPO_ROOT -WindowStyle Hidden
Start-Process "python" -ArgumentList "$REPO_ROOT\scripts\deputy_chat_processor.py", "$REPO_ROOT" -WorkingDirectory $REPO_ROOT -WindowStyle Hidden

Write-Host "SYSTEM RECOVERED." -ForegroundColor Cyan
