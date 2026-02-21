function Initialize-RunScripts([string]$TargetRunDir, [string[]]$Team, [string]$RawPath, [string]$BaseRepo) {
  Log-Line "Orchestrator: Generating V2 NATIVE execution scripts for team: $($Team -join ', ')"
  $i = 1
  # Ensure target run dir is absolute and correctly formatted
  $absRunDir = [System.IO.Path]::GetFullPath($TargetRunDir)
  $absBase = [System.IO.Path]::GetFullPath($BaseRepo)
  
  foreach ($role in $Team) {
    $promptPath = Join-Path $absRunDir "state\prompt$i.txt"
    $outMd = Join-Path $absRunDir "agent$i.md"
    $ps1 = Join-Path $absRunDir "run-agent$i.ps1"
    $runnerScript = Join-Path $absBase "scripts\agent_runner_v2.py" # USE V2 RUNNER EXPLICITLY

    if (-not (Test-Path $promptPath)) {
        "You are Agent $i. Role: $role`nMission context is in the root directory." | Set-Content -Path $promptPath -Encoding UTF8
    }

    # NATIVE PYTHON RUNNER V2 - SERVICE ACCOUNT AUTH
    $content = @"
`$ErrorActionPreference = 'Stop'
python "$runnerScript" "$promptPath" "$outMd"
if (`$LASTEXITCODE -ne 0) { exit 1 }
"@
    $content | Set-Content -Path $ps1 -Encoding UTF8
    Log-Line "Generated: run-agent$i.ps1 ($role) [SERVICE ACCOUNT V2]"
    $i++
  }
}