param([string]$AgentName, [string]$Task)

$logDir = '.gemini/ipc'
$LogPath = Join-Path $logDir "$AgentName.log"
$StatusPath = Join-Path $logDir "$AgentName.status"

'RUNNING' | Out-File -Force -FilePath $StatusPath

Start-Process -FilePath 'gemini' -ArgumentList 'exec', '--agent', $AgentName, '--prompt', "\"`$Task`\"" -RedirectStandardOutput $LogPath -WindowStyle Hidden

Write-Host "Success: Spawned $AgentName. Monitor $LogPath for output."
