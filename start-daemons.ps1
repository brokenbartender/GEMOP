param(
  [ValidateSet('default','dev','browser','research','ops','fidelity','full','screen-readonly','screen-operator','sidecar-operator')]
  [string]$Profile = 'default'
)

$ErrorActionPreference = 'Stop'

function Test-Listening([int]$Port) {
  return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Ensure-ProcessOnPort {
  param(
    [Parameter(Mandatory=$true)][int]$Port,
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string]$FilePath,
    [Parameter(Mandatory=$true)][string[]]$ArgumentList,
    [Parameter(Mandatory=$false)][string]$WorkingDirectory = $null,
    [Parameter(Mandatory=$false)][string]$StdoutPath = $null,
    [Parameter(Mandatory=$false)][string]$StderrPath = $null
  )

  if (Test-Listening $Port) {
    Write-Host " -> $Name already listening on :$Port"
    return
  }

  Write-Host " -> starting $Name on :$Port"

  $psi = @{
    FilePath = $FilePath
    ArgumentList = $ArgumentList
    WindowStyle = 'Hidden'
  }
  if ($WorkingDirectory) { $psi.WorkingDirectory = $WorkingDirectory }
  if ($StdoutPath) { $psi.RedirectStandardOutput = $StdoutPath }
  if ($StderrPath) { $psi.RedirectStandardError = $StderrPath }

  Start-Process @psi | Out-Null

  $deadline = (Get-Date).AddSeconds(15)
  while ((Get-Date) -lt $deadline) {
    if (Test-Listening $Port) {
      Write-Host "    $Name is listening"
      return
    }
    Start-Sleep -Milliseconds 250
  }

  Write-Warning "$Name did not start listening on :$Port within 15s (check logs)."
}

$logDir = Join-Path $PSScriptRoot "logs"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }

Write-Host "Starting MCP daemons for profile: $Profile"

if ($Profile -in @('browser','research','fidelity','full')) {
  $proxyWorkDir = Join-Path $PSScriptRoot "mcp-daemons"
  $proxyScript = Join-Path $proxyWorkDir 'stdio-streamable-http-proxy.mjs'

  if (!(Test-Path $proxyScript)) {
    throw "Missing proxy script: $proxyScript"
  }

  $dataDir = Join-Path $PSScriptRoot "data"
  if (!(Test-Path $dataDir)) { New-Item -ItemType Directory -Force -Path $dataDir | Out-Null }
  $memoryFile = Join-Path $dataDir 'memory.jsonl'

  # Use pinkpixel memory server for better reliability
  $memoryArgs = @('/c', "node ""$proxyScript"" --command npx --name memory --port 3013 --endpoint /mcp --args ""-y @pinkpixel/memory-mcp@latest"" --env MEMORY_FILE_PATH=""$memoryFile""")
  Ensure-ProcessOnPort -Port 3013 -Name 'memory' `
    -FilePath 'cmd.exe' `
    -ArgumentList $memoryArgs `
    -WorkingDirectory $proxyWorkDir `
    -StdoutPath (Join-Path $logDir 'memory-daemon.out.log') `
    -StderrPath (Join-Path $logDir 'memory-daemon.err.log')

  Ensure-ProcessOnPort -Port 8931 -Name 'playwright' `
    -FilePath 'cmd.exe' `
    -ArgumentList @('/c', 'playwright-mcp.cmd --headless --port 8931') `
    -WorkingDirectory $PSScriptRoot `
    -StdoutPath (Join-Path $logDir 'playwright-daemon.out.log') `
    -StderrPath (Join-Path $logDir 'playwright-daemon.err.log')

  if ($Profile -in @('research','full')) {
    $py = "python"
    $fastembedCache = Join-Path $dataDir 'fastembed_cache'
    if (!(Test-Path $fastembedCache)) { New-Item -ItemType Directory -Force -Path $fastembedCache | Out-Null }

    # Use local shim for semantic search
    $shimPath = Join-Path $PSScriptRoot "mcp\semantic_server.py"
    $searchArgs = @('/c', "node ""$proxyScript"" --command ""$py"" --name semantic-search --port 3014 --endpoint /mcp --args ""$shimPath"" --env FASTEMBED_CACHE_PATH=""$fastembedCache""")
    Ensure-ProcessOnPort -Port 3014 -Name 'semantic-search' `
      -FilePath 'cmd.exe' `
      -ArgumentList $searchArgs `
      -WorkingDirectory $PSScriptRoot `
      -StdoutPath (Join-Path $logDir 'semantic-search-daemon.out.log') `
      -StderrPath (Join-Path $logDir 'semantic-search-daemon.err.log')
  }
} else {
  Write-Host " -> no daemons needed for this profile"
}
