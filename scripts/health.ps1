param(
  [ValidateSet('default','dev','browser','research','ops','fidelity','full','screen-readonly','screen-operator','sidecar-operator')]
  [string]$Profile = 'research',

  [switch]$StartDaemons
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPy = Join-Path $repoRoot '.venv\Scripts\python.exe'
$python = 'python'
if (Test-Path $venvPy) { $python = $venvPy }
$caller = Join-Path $repoRoot 'mcp-daemons\mcp-call.mjs'
$startDaemonsScript = Join-Path $repoRoot 'start-daemons.ps1'

function Fail($msg) {
  Write-Host ("FAIL: {0}" -f $msg) -ForegroundColor Red
  $script:hadFailure = $true
}

function Ok($msg) {
  Write-Host ("OK:   {0}" -f $msg) -ForegroundColor Green
}

function Warn($msg) {
  Write-Host ("WARN: {0}" -f $msg) -ForegroundColor Yellow
}

function Cleanup-StaleLockFiles {
  $locksRoot = Join-Path $repoRoot 'state\locks'
  if (-not (Test-Path $locksRoot)) {
    return
  }

  $removed = 0
  $lockFiles = Get-ChildItem $locksRoot -File -Filter '*.lock' -ErrorAction SilentlyContinue
  foreach ($lock in $lockFiles) {
    $raw = ''
    try { $raw = (Get-Content -Raw $lock.FullName -ErrorAction Stop) } catch { continue }
    $pid = $null
    if ($raw -match 'pid=(\d+)') {
      try { $pid = [int]$matches[1] } catch { $pid = $null }
    }
    $shouldRemove = $false
    if ($pid) {
      $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
      if (-not $proc) { $shouldRemove = $true }
    } else {
      $ageHours = ((Get-Date) - $lock.LastWriteTime).TotalHours
      if ($ageHours -gt 24) { $shouldRemove = $true }
    }
    if ($shouldRemove) {
      try {
        Remove-Item -Force $lock.FullName -ErrorAction Stop
        $removed += 1
        Ok ("Removed stale lock: {0}" -f $lock.Name)
      } catch {
        Fail ("Unable to remove stale lock {0}: {1}" -f $lock.Name, $_.Exception.Message)
      }
    }
  }

  $stateRoot = Join-Path $repoRoot 'ramshare\state'
  if (Test-Path $stateRoot) {
    $pidFiles = Get-ChildItem $stateRoot -File -Filter 'watchdog.*.pid' -ErrorAction SilentlyContinue
    foreach ($pf in $pidFiles) {
      $pid = $null
      try { $pid = [int]((Get-Content -Raw $pf.FullName).Trim()) } catch { $pid = $null }
      if ($pid) {
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if (-not $proc) {
          try {
            Remove-Item -Force $pf.FullName -ErrorAction Stop
            $removed += 1
            Ok ("Removed stale pid file: {0}" -f $pf.Name)
          } catch {
            Fail ("Unable to remove stale pid file {0}: {1}" -f $pf.Name, $_.Exception.Message)
          }
        }
      }
    }
  }

  if ($removed -eq 0) {
    Ok "No stale lock/pid files detected"
  }
}

$hadFailure = $false
Write-Host "Health check (profile=$Profile)"
Cleanup-StaleLockFiles

# Basic dependencies
try { $null = (Get-Command $python -ErrorAction Stop); Ok "python is available ($python)" } catch { Fail "python not found in PATH and no .venv detected" }
try { $null = (Get-Command node -ErrorAction Stop); Ok "node is available" } catch { Fail "node not found in PATH" }
try { $null = (Get-Command rg -ErrorAction Stop); Ok "rg (ripgrep) is available" } catch { Fail "rg not found in PATH (optional but recommended)" }
try { $null = (Get-Command git -ErrorAction Stop); Ok "git is available" } catch { Fail "git not found in PATH" }
if (Test-Path $caller) { Ok "MCP caller present ($caller)" } else { Fail "Missing MCP caller ($caller)" }

# Local model backend (Ollama) is optional, but council local runs depend on it.
try {
  $ollamaOk = $false
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2
    if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) { $ollamaOk = $true }
  } catch { $ollamaOk = $false }
  $requireOllama = (($env:GEMINI_OP_HEALTH_REQUIRE_OLLAMA) -or '').Trim().ToLower() -in @('1','true','yes')
  if ($ollamaOk) {
    Ok "Ollama reachable (http://127.0.0.1:11434)"
  } else {
    if ($requireOllama) { Fail "Ollama not reachable (start Ollama if you want local model runs)" } else { Warn "Ollama not reachable (local model runs will fail/fallback)" }
  }
} catch { }

# Expected daemons by profile
$daemonChecks = New-Object System.Collections.Generic.List[object]
if ($Profile -in @('browser','research','fidelity','full')) {
  $daemonChecks.Add([pscustomobject]@{ Name = 'memory'; Url = 'http://localhost:3013/mcp' }) | Out-Null
}
if ($Profile -in @('research','full')) {
  $daemonChecks.Add([pscustomobject]@{ Name = 'semantic-search'; Url = 'http://localhost:3014/mcp' }) | Out-Null
}
if ($Profile -in @('browser','full')) {
  $daemonChecks.Add([pscustomobject]@{ Name = 'playwright'; Url = 'http://localhost:8931/mcp' }) | Out-Null
}

if ($StartDaemons) {
  if (Test-Path $startDaemonsScript) {
    Write-Host "Starting/ensuring daemons..."
    & $startDaemonsScript -Profile $Profile | Out-Null
  } else {
    Fail "Missing daemon starter script ($startDaemonsScript)"
  }
}

foreach ($d in $daemonChecks) {
  Write-Host ("Checking MCP daemon: {0} ({1})" -f $d.Name, $d.Url)
  try {
    & node $caller --url $d.Url --tool __list_tools__ --json '{}' *> $null
    if ($LASTEXITCODE -eq 0) {
      Ok ("{0} responded to tools/list" -f $d.Name)
    } else {
      Fail ("{0} tools/list failed (exit=$LASTEXITCODE)" -f $d.Name)
    }
  } catch {
    Fail ("{0} tools/list threw: {1}" -f $d.Name, $_.Exception.Message)
  }
}

if ($hadFailure) {
  Write-Host ""
  Write-Host "Health check failed." -ForegroundColor Red
  exit 1
}

Write-Host ""
Write-Host "Health check passed." -ForegroundColor Green
exit 0
