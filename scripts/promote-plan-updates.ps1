param(
  [string]$PendingPath = 'C:\Gemini\ramshare\plan-updates\pending.md',
  [string]$PlanPath = 'C:\Gemini\ramshare\progressive-plan.md'
)

$ErrorActionPreference = 'Stop'

if (!(Test-Path $PendingPath)) {
  Write-Host "No pending file: $PendingPath"
  exit 0
}
if (!(Test-Path $PlanPath)) {
  Write-Host "Missing plan file: $PlanPath"
  exit 1
}

$pending = Get-Content -Path $PendingPath -Raw -ErrorAction Stop
$lines = $pending -split "`r?`n"

$toPromote = New-Object System.Collections.Generic.List[string]
$kept = New-Object System.Collections.Generic.List[string]

foreach ($l in $lines) {
  if ($l -match '^[ \t]*PROMOTE:[ \t]*(.+)$') {
    $toPromote.Add($Matches[1]) | Out-Null
  } else {
    $kept.Add($l) | Out-Null
  }
}

if ($toPromote.Count -eq 0) {
  Write-Host "No PROMOTE: lines found."
  exit 0
}

$stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
$block = New-Object System.Collections.Generic.List[string]
$block.Add("") | Out-Null
$block.Add("## Promoted Updates ($stamp)") | Out-Null
foreach ($p in $toPromote) {
  $block.Add(("- {0}" -f $p.Trim())) | Out-Null
}
$block.Add("") | Out-Null

Add-Content -Path $PlanPath -Value ($block -join "`n") -Encoding UTF8
Set-Content -Path $PendingPath -Value ($kept -join "`n") -NoNewline -Encoding UTF8

Write-Host ("Promoted {0} line(s) into {1}" -f $toPromote.Count, $PlanPath)
exit 0

