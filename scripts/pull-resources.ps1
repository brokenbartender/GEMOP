param(
  [switch]$Force
)

$ErrorActionPreference = 'Stop'

$root = 'C:\Gemini'
$resRoot = Join-Path $root 'ramshare\resources'
$pdfDir = Join-Path $resRoot 'pdf'
$webDir = Join-Path $resRoot 'web'
$sourcesJson = Join-Path $resRoot 'sources.json'
$manifest = Join-Path $resRoot 'manifest.md'

New-Item -ItemType Directory -Force -Path $pdfDir | Out-Null
New-Item -ItemType Directory -Force -Path $webDir | Out-Null

function Download-IfMissing {
  param(
    [Parameter(Mandatory=$true)][string]$Url,
    [Parameter(Mandatory=$true)][string]$OutFile
  )
  if ((-not $Force) -and (Test-Path $OutFile)) {
    Write-Host "skip (exists): $OutFile"
    return
  }
  Write-Host "download: $Url -> $OutFile"
  try {
    $tmp = "$OutFile.tmp.$PID"
    Invoke-WebRequest -Uri $Url -OutFile $tmp -UseBasicParsing -TimeoutSec 300 -Headers @{ 'User-Agent' = 'Gemini-op' }
    Move-Item -Force -Path $tmp -Destination $OutFile
  } catch {
    Write-Host "WARN: download failed: $Url ($($_.Exception.Message))"
  }
}

function Snapshot-IfMissing {
  param(
    [Parameter(Mandatory=$true)][string]$Url,
    [Parameter(Mandatory=$true)][string]$OutFile
  )
  if ((-not $Force) -and (Test-Path $OutFile)) {
    Write-Host "skip (exists): $OutFile"
    return
  }
  Write-Host "snapshot: $Url -> $OutFile"
  try {
    $tmp = "$OutFile.tmp.$PID"
    Invoke-WebRequest -Uri $Url -OutFile $tmp -UseBasicParsing -TimeoutSec 120 -Headers @{ 'User-Agent' = 'Gemini-op' }
    Move-Item -Force -Path $tmp -Destination $OutFile
  } catch {
    Write-Host "WARN: snapshot failed: $Url ($($_.Exception.Message))"
  }
}

# Sources (prefer ramshare/resources/sources.json so you can add links without editing this script)
if (Test-Path $sourcesJson) {
  $sources = Get-Content -Path $sourcesJson -Raw | ConvertFrom-Json

  foreach ($p in ($sources.pdf | Where-Object { $_.url -and $_.out })) {
    $outFile = Join-Path $resRoot $p.out
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outFile) | Out-Null
    Download-IfMissing -Url $p.url -OutFile $outFile
  }

  foreach ($h in ($sources.html | Where-Object { $_.url -and $_.out })) {
    $outFile = Join-Path $resRoot $h.out
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outFile) | Out-Null
    Snapshot-IfMissing -Url $h.url -OutFile $outFile
  }
} else {
  # Fallback: minimal built-in defaults.
  Download-IfMissing `
    -Url 'https://www.microsoft.com/en-us/research/uploads/prod/2006/01/Bishop-Pattern-Recognition-and-Machine-Learning-2006.pdf' `
    -OutFile (Join-Path $pdfDir 'bishop-prml-2006.pdf')

  $pages = @{
    'deeplearningbook.html'     = 'https://www.deeplearningbook.org/'
    'aima.html'                 = 'https://aima.cs.berkeley.edu/'
    'd2l.html'                  = 'https://d2l.ai/'
    'artint3e.html'             = 'https://artint.info/3e/html/ArtInt3e.html'
    'probml-book1.html'         = 'https://probml.github.io/pml-book/book1.html'
    'understanding-ml.html'     = 'https://www.cs.huji.ac.il/~shais/UnderstandingMachineLearning/'
    'mml-book.html'             = 'https://mml-book.github.io/'
  }

  foreach ($name in $pages.Keys) {
    Snapshot-IfMissing -Url $pages[$name] -OutFile (Join-Path $webDir $name)
  }
}

# Best-effort manifest regeneration (derived from sources.json if present).
try {
  $lines = New-Object System.Collections.Generic.List[string]
  $lines.Add("# Resource Manifest") | Out-Null
  $lines.Add("") | Out-Null
  $lines.Add("All dates are local time.") | Out-Null
  $lines.Add("") | Out-Null

  if (Test-Path $sourcesJson) {
    $sources = Get-Content -Path $sourcesJson -Raw | ConvertFrom-Json

    $lines.Add("## PDFs") | Out-Null
    foreach ($p in ($sources.pdf | Where-Object { $_.out })) {
      $path = Join-Path 'ramshare/resources' $p.out
      $localPath = Join-Path $resRoot $p.out
      $retrieved = if (Test-Path $localPath) { (Get-Item $localPath).LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') } else { 'missing' }
      $lines.Add(('- `{0}`' -f $path)) | Out-Null
      $lines.Add(('  - Source: `{0}`' -f $p.url)) | Out-Null
      $lines.Add(("  - Retrieved: {0}" -f $retrieved)) | Out-Null
      if ($p.notes) { $lines.Add(("  - Notes: {0}" -f $p.notes)) | Out-Null }
      $lines.Add("") | Out-Null
    }

    $lines.Add("## HTML Snapshots (Landing Pages)") | Out-Null
    foreach ($h in ($sources.html | Where-Object { $_.out })) {
      $path = Join-Path 'ramshare/resources' $h.out
      $localPath = Join-Path $resRoot $h.out
      $retrieved = if (Test-Path $localPath) { (Get-Item $localPath).LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') } else { 'missing' }
      $lines.Add(('- `{0}`' -f $path)) | Out-Null
      $lines.Add(('  - Source: `{0}`' -f $h.url)) | Out-Null
      $lines.Add(("  - Retrieved: {0}" -f $retrieved)) | Out-Null
      if ($h.notes) { $lines.Add(("  - Notes: {0}" -f $h.notes)) | Out-Null }
      $lines.Add("") | Out-Null
    }

    if ($sources.record_only) {
      $lines.Add("## Recorded Only (Unverified / Do Not Auto-Fetch)") | Out-Null
      foreach ($r in $sources.record_only) {
        $lines.Add(('- `{0}`' -f $r.id)) | Out-Null
        $lines.Add(('  - Source: `{0}`' -f $r.url)) | Out-Null
        if ($r.notes) { $lines.Add(("  - Notes: {0}" -f $r.notes)) | Out-Null }
        $lines.Add("") | Out-Null
      }
    }

    Set-Content -Path $manifest -Value ($lines -join "`n") -NoNewline
  }
} catch {
  Write-Host "WARN: failed to regenerate manifest: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "done: $(Get-ChildItem $resRoot -Recurse -File | Measure-Object | Select-Object -ExpandProperty Count) files"
