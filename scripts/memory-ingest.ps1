param(
  [Parameter(Mandatory = $true)]
  [string]$DistilledNotePath,

  [string]$MemoryUrl = 'http://localhost:3013/mcp'
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$caller = Join-Path $repoRoot 'mcp-daemons\mcp-call.mjs'
$mcpDaemonsDir = Join-Path $repoRoot 'mcp-daemons'
$mcpSdkPath = Join-Path $mcpDaemonsDir 'node_modules\@modelcontextprotocol\sdk\package.json'

function Ensure-McpCallerDependencies {
  if (Test-Path $mcpSdkPath) { return }
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "Missing npm; cannot install mcp-daemons dependencies."
    exit 1
  }
  if (-not (Test-Path (Join-Path $mcpDaemonsDir 'package.json'))) {
    Write-Error "Missing mcp-daemons package.json at $mcpDaemonsDir"
    exit 1
  }
  Push-Location $mcpDaemonsDir
  try {
    if (Test-Path (Join-Path $mcpDaemonsDir 'package-lock.json')) {
      & npm ci *> $null
    } else {
      & npm install *> $null
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $mcpSdkPath)) {
      Write-Error "Failed to install @modelcontextprotocol/sdk for memory ingest."
      exit 1
    }
  } finally {
    Pop-Location
  }
}

if (!(Test-Path $DistilledNotePath)) {
  Write-Error "Missing distilled note: $DistilledNotePath"
  exit 1
}
if (!(Test-Path $caller)) {
  Write-Error "Missing MCP caller: $caller"
  exit 1
}

Ensure-McpCallerDependencies

$txt = Get-Content -Path $DistilledNotePath -Raw -ErrorAction Stop
$lines = $txt -split "`r?`n" | Where-Object { $_ -and $_.Trim().Length -gt 0 }

$title = ($lines | Where-Object { $_ -match '^# ' } | Select-Object -First 1)
if (-not $title) { $title = "# Distilled Note" }
$name = ($DistilledNotePath -replace '^.*\\\\','') -replace '\\.md$',''

# Keep observations bounded; memory is for retrieval, not full document storage.
$obs = New-Object System.Collections.Generic.List[string]
$obs.Add(("source_path: {0}" -f $DistilledNotePath)) | Out-Null
$obs.Add(("title: {0}" -f ($title -replace '^#\\s*',''))) | Out-Null

foreach ($l in ($lines | Select-Object -First 60)) {
  if ($l -match '^# ') { continue }
  $obs.Add($l) | Out-Null
}

$payload = @{
  entities = @(
    @{
      name = $name
      entityType = 'distilled_note'
      observations = $obs
    }
  )
} | ConvertTo-Json -Depth 8

& node $caller --url $MemoryUrl --tool create_entities --json $payload *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Error "Memory ingest failed (exit=$LASTEXITCODE)"
  exit 1
}

Write-Host "MEMORY: upserted $name"

