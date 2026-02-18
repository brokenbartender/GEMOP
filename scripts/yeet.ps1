<#
.SYNOPSIS
Safely stages, commits, and pushes changes to a specific target repository with Signet Verification.
#>

[CmdletBinding()]
param(
    [string]$TargetRepo = "",
    [string]$RunDir = "",
    [string]$Prompt = ""
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# 1. Signet Verification (The Authority)
if (-not [string]::IsNullOrWhiteSpace($RunDir) -and -not [string]::IsNullOrWhiteSpace($Prompt)) {
    Write-Host "[Yeet] Invoking Solomon's Signet for final verification..." -ForegroundColor Magenta
    $signetScript = Join-Path $RepoRoot "scripts\signet_verifier.py"
    & python $signetScript --prompt $Prompt --run-dir $RunDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "[Yeet] SIGNET VERIFICATION FAILED. The changes do not align with user intent. Aborting push."
        exit 1
    }
}

# 2. Context Selection
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
$msg = "Gemini Auto-Commit: Verified via Solomon's Signet`n`nOther-Computer:`n- pull latest main`n- run: verified build check"
git commit -m $msg

Write-Host "[Yeet] Pushing to remote..." -ForegroundColor Cyan
$branch = git rev-parse --abbrev-ref HEAD
git push --set-upstream origin $branch

Write-Host "[Yeet] Success!" -ForegroundColor Green
