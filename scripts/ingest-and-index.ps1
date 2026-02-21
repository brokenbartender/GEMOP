param(
  [ValidateSet('dev','browser','research','ops','full')]
  [string]$Profile = 'research',

  [switch]$ForceRefresh,
  [switch]$ForceExtract,
  [switch]$ForceReindex,

  # For evidence drops, we don't want to re-download the whole resources catalog.
  [switch]$SkipRefreshResources,

  # Semantic-search initialize is for code index; it is slow and usually not needed for evidence ingestion.
  [switch]$SkipSemanticReindex
)

$ErrorActionPreference = 'Stop'

$repoRoot = ($env:GEMINI_OP_REPO_ROOT)
if ([string]::IsNullOrWhiteSpace($repoRoot)) {
  $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$venvPy = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (!(Test-Path $venvPy)) {
  $venvPy = 'python'
}
$pullResources = Join-Path $repoRoot 'scripts\pull-resources.ps1'
$extractDocs = Join-Path $repoRoot 'scripts\extract-docs.py'
$notesRaw = Join-Path $repoRoot 'ramshare\notes\raw'
$notesDistilled = Join-Path $repoRoot 'ramshare\notes\distilled'
$evidenceInbox = Join-Path $repoRoot 'ramshare\evidence\inbox'

New-Item -ItemType Directory -Force -Path $notesRaw | Out-Null
New-Item -ItemType Directory -Force -Path $notesDistilled | Out-Null
New-Item -ItemType Directory -Force -Path $evidenceInbox | Out-Null

Write-Host "Profile: $Profile"

Write-Host ""
Write-Host "[1/4] Refresh resources"
if ($SkipRefreshResources) {
  Write-Host "skip (requested): refresh resources"
} else {
  if ($ForceRefresh) {
    & $pullResources -Force
  } else {
    & $pullResources
  }
}

Write-Host ""
Write-Host "[2/4] Extract PDFs and HTML snapshots -> ramshare/notes/raw"

function Needs-Update($src, $dst) {
  if ($ForceExtract) { return $true }
  if (!(Test-Path $dst)) { return $true }
  return ((Get-Item $src).LastWriteTimeUtc -gt (Get-Item $dst).LastWriteTimeUtc)
}

$inputs = @()
$inputs += Get-ChildItem -Path (Join-Path $repoRoot 'ramshare\resources') -Recurse -File -Filter *.pdf -ErrorAction SilentlyContinue
$inputs += Get-ChildItem -Path (Join-Path $repoRoot 'ramshare\resources') -Recurse -File -Filter *.html -ErrorAction SilentlyContinue
$inputs += Get-ChildItem -Path $evidenceInbox -Recurse -File -Filter *.pdf -ErrorAction SilentlyContinue
$inputs += Get-ChildItem -Path $evidenceInbox -Recurse -File -Filter *.html -ErrorAction SilentlyContinue
$inputs += Get-ChildItem -Path $evidenceInbox -Recurse -File -Filter *.txt -ErrorAction SilentlyContinue
$inputs += Get-ChildItem -Path $evidenceInbox -Recurse -File -Filter *.md -ErrorAction SilentlyContinue

foreach ($f in $inputs) {
  $safe = ($f.FullName.Substring($repoRoot.Length).TrimStart('\') -replace '[\\\\/:*?\"<>| ]','_')
  $out = Join-Path $notesRaw ($safe + '.txt')
  if (Needs-Update $f.FullName $out) {
    Write-Host " extract: $($f.FullName) -> $out"
    if ($f.Extension -in @('.txt', '.md')) {
      # Keep local evidence ingestion simple: treat text/markdown as already-extracted.
      $raw = Get-Content -Path $f.FullName -Raw -ErrorAction Stop
      Set-Content -Path $out -Value $raw -NoNewline
    } else {
      & $venvPy $extractDocs --in $f.FullName --out $out
    }
  }
}

Write-Host ""
Write-Host "[3/4] Ensure daemons and trigger semantic-search reindex (if available)"
& (Join-Path $repoRoot 'start-daemons.ps1') -Profile $Profile | Out-Null

# Semantic-search is only expected in research/full.
$semanticUrl = 'http://localhost:3014/mcp'
$caller = Join-Path $repoRoot 'mcp-daemons\mcp-call.mjs'
if ($SkipSemanticReindex) {
  Write-Host " skip (requested): semantic-search initialize"
} elseif (Test-Path $caller) {
  try {
    $toolName = if ($ForceReindex) { 'initialize' } else { 'initialize' }
    $payload = if ($ForceReindex) { '{"force_reindex":true}' } else { '{"force_reindex":false}' }
    Write-Host " semantic-search: calling $toolName on $semanticUrl payload=$payload"
    # Run in background; initial indexing can take a while and we don't want to block ingestion.
    $logDir = Join-Path $repoRoot 'logs'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $outLog = Join-Path $logDir 'semantic-search-initialize.out.log'
    $errLog = Join-Path $logDir 'semantic-search-initialize.err.log'

    Start-Process -FilePath 'node' -ArgumentList @(
      $caller,
      '--url', $semanticUrl,
      '--tool', $toolName,
      '--json', $payload
    ) -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog | Out-Null
  } catch {
    Write-Host "WARN: semantic-search initialize failed: $($_.Exception.Message)"
  }
} else {
  Write-Host "WARN: missing caller script: $caller"
}

Write-Host ""
Write-Host "[4/4] Generate agent task stubs for un-distilled notes"
$tasksDir = Join-Path $repoRoot 'ramshare\agent-tasks'
New-Item -ItemType Directory -Force -Path $tasksDir | Out-Null

$rawNotes = Get-ChildItem -Path $notesRaw -File -Filter *.txt -ErrorAction SilentlyContinue
foreach ($n in $rawNotes) {
  $base = $n.BaseName
  $dist = Join-Path $notesDistilled ($base + '.md')
  if (!(Test-Path $dist)) {
    $task = Join-Path $tasksDir ($base + '.md')
    if (!(Test-Path $task)) {
      $lines = New-Object System.Collections.Generic.List[string]
      $lines.Add(("# Distill: {0}" -f $n.Name)) | Out-Null
      $lines.Add("") | Out-Null
      $lines.Add(('Source: `{0}`' -f $n.FullName)) | Out-Null
      $lines.Add("") | Out-Null
      $lines.Add("## Output Needed") | Out-Null
      $lines.Add("- Summary (10 bullets max)") | Out-Null
      $lines.Add("- Actionable controls/checks (prioritized P0/P1/P2)") | Out-Null
      $lines.Add("- Mapping to Gemini-op components:") | Out-Null
      $lines.Add("  - profiles (`config/profiles/config.*.toml`)") | Out-Null
      $lines.Add("  - MCP daemons (`start-daemons.ps1`)") | Out-Null
      $lines.Add("  - policies/logging/secrets") | Out-Null
      $lines.Add("") | Out-Null
      $lines.Add("## Produce") | Out-Null
      $lines.Add(('- Write distilled note to: `{0}`' -f $dist)) | Out-Null
      $lines.Add("") | Out-Null

      Set-Content -Path $task -Value ($lines -join "`n") -NoNewline
    }
  }
}

Write-Host "done"
