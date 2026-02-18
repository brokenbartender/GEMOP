param(
  [string]$RepoRoot = ""
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = (Resolve-Path .).Path
}

function Say([string]$k, [string]$v) {
  Write-Host ("{0,-24} {1}" -f $k, $v)
}

Say "repo" $RepoRoot

try {
  $py = (python -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1).Trim()
  if ($py) { Say "python" $py }
} catch {}

try {
  $ssh = (Get-Command ssh -ErrorAction SilentlyContinue)
  if ($ssh) { Say "ssh" $ssh.Source }
} catch {}

try {
  $wsl = (Get-Command wsl -ErrorAction SilentlyContinue)
  if ($wsl) {
    Say "wsl" $wsl.Source
    $list = (wsl -l -v 2>$null)
    if ($list) {
      Write-Host ""
      Write-Host "WSL distros:"
      $list
    }
  }
} catch {}

Say "REMOTE_EXEC_ENABLE" ($env:GEMINI_OP_REMOTE_EXEC_ENABLE ?? "")
Say "A2A_SHARED_SECRET" ([string]::IsNullOrWhiteSpace($env:GEMINI_OP_A2A_SHARED_SECRET) -and [string]::IsNullOrWhiteSpace($env:AGENTIC_A2A_SHARED_SECRET) ? "" : "(set)")

$peers = Join-Path $RepoRoot "ramshare\state\a2a\peers.json"
if (Test-Path $peers) {
  Say "peers.json" $peers
  try {
    $txt = Get-Content -Raw $peers
    $obj = $txt | ConvertFrom-Json
    $names = @()
    foreach ($p in $obj.PSObject.Properties) { $names += $p.Name }
    Say "peers" ($names -join ", ")
  } catch {
    Say "peers_parse" ("ERROR: " + $_.Exception.Message)
  }
} else {
  Say "peers.json" "missing"
}

$inbox = Join-Path $RepoRoot "ramshare\state\a2a\inbox"
if (Test-Path $inbox) {
  $n = (Get-ChildItem -Path $inbox -Filter *.json -File -ErrorAction SilentlyContinue | Measure-Object).Count
  Say "inbox_depth" "$n"
}

Write-Host ""
Write-Host "Suggested next command (local exec path):"
Write-Host "  `$env:GEMINI_OP_REMOTE_EXEC_ENABLE='1'; python .\\scripts\\a2a_remote_executor.py"
Write-Host ""
Write-Host "Suggested next command (WSL exec path):"
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\start-a2a-executor-wsl.ps1"
