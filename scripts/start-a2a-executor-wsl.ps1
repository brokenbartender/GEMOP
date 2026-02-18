param(
  [string]$Distro = 'Ubuntu',
  [switch]$Once
)

$ErrorActionPreference = 'Stop'

function To-WslPath([string]$WinPath) {
  $p = (Resolve-Path $WinPath).Path
  if ($p -match '^([A-Za-z]):\\(.*)$') {
    $drive = $matches[1].ToLower()
    $rest = ($matches[2] -replace '\\', '/')
    return "/mnt/$drive/$rest"
  }
  throw "Unsupported path for WSL conversion: $p"
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRootWsl = To-WslPath $RepoRoot

$logDir = Join-Path $RepoRoot 'logs'
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$outLog = Join-Path $logDir 'a2a_wsl_executor.out.log'
$errLog = Join-Path $logDir 'a2a_wsl_executor.err.log'

$cmd = "cd '$RepoRootWsl' && GEMINI_OP_REMOTE_EXEC_ENABLE=1 python3 scripts/a2a_remote_executor.py"
if ($Once) { $cmd += " --once" }

$args = @('-d', $Distro, '--', 'bash', '-lc', $cmd)
$proc = Start-Process -FilePath 'wsl.exe' -ArgumentList $args -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
Write-Host "Started WSL A2A executor (distro=$Distro, pid=$($proc.Id)). Logs: $outLog / $errLog"

