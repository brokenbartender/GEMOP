<#
.SYNOPSIS
The Djed Pillar: Stability & Heartbeat Monitor.
Continuously pings the active run to ensure the spine doesn't snap.
#>

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$focusFile = Join-Path $RepoRoot "ramshare\state\project_focus.txt"

Write-Host "[Djed] Raising the Pillar. Stability monitor active." -ForegroundColor Green

while ($true) {
    if (Test-Path $focusFile) {
        $runSlug = Get-Content $focusFile
        $runDir = Join-Path $RepoRoot ".agent-jobs\$runSlug"
        $logPath = Join-Path $runDir "triad_orchestrator.log"

        if (Test-Path $logPath) {
            # Check for recent activity (last 5 minutes)
            $lastWrite = (Get-Item $logPath).LastWriteTime
            $diff = (Get-Date) - $lastWrite

            if ($diff.TotalMinutes -gt 5) {
                Write-Host "[Djed] ALERT: Run $runSlug appears stalled (no log activity for 5m)." -ForegroundColor Yellow
                # In a full implementation, this would trigger a restart or notification.
            } else {
                Write-Host "[Djed] Backbone is stable. $runSlug is active." -ForegroundColor Gray
            }
        }
    }
    
    Start-Sleep -Seconds 60
}
