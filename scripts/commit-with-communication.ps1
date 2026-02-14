<#
.SYNOPSIS
Creates a structured commit message and commits it.

.DESCRIPTION
Writes a commit message to .git\COMMIT_EDITMSG.auto and runs `git commit -F`.
Designed for consistent operator-to-operator communication.

NOTE: This script does not log the message content (to avoid accidental leakage
of sensitive context). It only logs high-level status.
#>

#Requires -Version 5.1

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true, HelpMessage = 'Commit type (e.g., feat, fix, chore).')]
  [string]$Type,

  [Parameter(Mandatory = $true, HelpMessage = 'One-line summary.')]
  [string]$Summary,

  [Parameter(Mandatory = $true, HelpMessage = 'Context bullets.')]
  [string[]]$Context,

  [Parameter(Mandatory = $true, HelpMessage = 'Other-computer bullets.')]
  [string[]]$OtherComputer,

  [Parameter(HelpMessage = 'Repository root path. Defaults to the repo above /scripts.')]
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,

  [Parameter(HelpMessage = 'Need-from-other-computer bullets.')]
  [string[]]$NeedFromOtherComputer = @(
    'hostname',
    'active IPv4 address',
    'sshd status (Running/Stopped)',
    'repo path on disk',
    'exact command output/errors if a step failed'
  ),

  [Parameter(HelpMessage = 'Validation bullets.')]
  [string[]]$Validation = @('not provided')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'lib\common.ps1')

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.git') -PathType Container)) {
  throw "Not a git repo: $RepoRoot"
}

Assert-GeminiCommand -CommandName 'git'

function Add-Section {
  <#
  .SYNOPSIS
  Adds a titled bullet section to the commit message.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [System.Text.StringBuilder]$Builder,

    [Parameter(Mandatory = $true)]
    [string]$Title,

    [Parameter(Mandatory = $true)]
    [string[]]$Items
  )

  [void]$Builder.AppendLine(('{0}:' -f $Title))
  foreach ($i in $Items) { [void]$Builder.AppendLine(\"- $i\") }
  [void]$Builder.AppendLine('')
}

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine(('{0}: {1}' -f $Type, $Summary))
[void]$sb.AppendLine('')
Add-Section -Builder $sb -Title 'Context' -Items $Context
Add-Section -Builder $sb -Title 'Other-Computer' -Items $OtherComputer
Add-Section -Builder $sb -Title 'Need-From-Other-Computer' -Items $NeedFromOtherComputer
Add-Section -Builder $sb -Title 'Validation' -Items $Validation

$msgPath = Join-Path $RepoRoot '.git\COMMIT_EDITMSG.auto'
$sb.ToString() | Set-Content -LiteralPath $msgPath -Encoding UTF8

# Avoid printing commit message content to logs.
Write-Host \"Commit message written: $msgPath\"

[void](Invoke-GeminiGit -RepoRoot $RepoRoot -Args @('commit', '-F', $msgPath) -TimeoutSec 300 -Retries 1)

Write-Host 'Commit complete.'
