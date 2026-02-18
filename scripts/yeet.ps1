<#
.SYNOPSIS
Safely stages, commits, and pushes changes to a specific target repository.
#>

[CmdletBinding()]
param(
    [string]$TargetRepo = ""
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# Determine where to run git commands
$execDir = $RepoRoot
if (-not [string]::IsNullOrWhiteSpace($TargetRepo)) {
    if (Test-Path $TargetRepo) {
        $execDir = (Resolve-Path $TargetRepo).Path
        Write-Host "[Yeet] Switching to target repo: $execDir" -ForegroundColor Yellow
    } else {
        Write-Error "Target repo path not found: $TargetRepo"
        exit 1
    }
}

Set-Location $execDir

Write-Host "[Yeet] Staging changes in $execDir..." -ForegroundColor Cyan
git add .

$status = git status --porcelain
if (-not $status) {
    Write-Host "[Yeet] No changes found in $execDir to commit." -ForegroundColor Yellow
    exit 0
}

Write-Host "[Yeet] Committing..." -ForegroundColor Cyan
$msg = "Gemini Auto-Commit: External Project Improvement`n`nOther-Computer:`n- pull latest main`n- run: automated build/test check"
git commit -m $msg

Write-Host "[Yeet] Pushing to remote..." -ForegroundColor Cyan
git push

Write-Host "[Yeet] Success!" -ForegroundColor Green
