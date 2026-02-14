param()

$ErrorActionPreference = 'Stop'

$repo = 'C:\Gemini'
$template = Join-Path $repo '.gitmessage.txt'
$hooksPath = Join-Path $repo '.githooks'

if (!(Test-Path $template)) { throw "Missing template: $template" }
if (!(Test-Path $hooksPath)) { throw "Missing hooks path: $hooksPath" }

git -C $repo config commit.template $template
git -C $repo config core.hooksPath $hooksPath

Write-Host "Configured git commit policy:"
Write-Host " - commit.template = $template"
Write-Host " - core.hooksPath = $hooksPath"

