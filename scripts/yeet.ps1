<#
.SYNOPSIS
Safely stages, commits, and pushes changes to the remote repository.
#>

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

Write-Host "[Yeet] Staging all changes..." -ForegroundColor Cyan
git add .

$status = git status --porcelain
if (-not $status) {
    Write-Host "[Yeet] No changes to commit." -ForegroundColor Yellow
    exit 0
}

Write-Host "[Yeet] Committing..." -ForegroundColor Cyan
$msg = "Gemini Auto-Commit: Architecture Upgrade`n`nOther-Computer:`n- pull latest main`n- run: pwsh scripts/health.ps1 -Profile full"
git commit -m $msg

Write-Host "[Yeet] Pushing to remote..." -ForegroundColor Cyan
git push

Write-Host "[Yeet] Success!" -ForegroundColor Green
