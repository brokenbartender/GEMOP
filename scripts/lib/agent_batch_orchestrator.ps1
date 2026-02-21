<#
.SYNOPSIS
Deprecated wrapper for the triad orchestrator.

.DESCRIPTION
This script is kept for backward compatibility. Use:
  scripts\triad_orchestrator.ps1

It forwards all arguments to triad_orchestrator.ps1.
#>

#Requires -Version 5.1

& (Join-Path $PSScriptRoot 'triad_orchestrator.ps1') @args
exit $LASTEXITCODE
