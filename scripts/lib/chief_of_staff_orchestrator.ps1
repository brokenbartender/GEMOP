param(
    [string]$Prompt,
    [string]$RepoRoot = $PSScriptRoot
)

$ErrorActionPreference = 'Stop'
Set-Location $RepoRoot

# Initialize Run Directory
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $RepoRoot ".agent-jobs\job-$timestamp"
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
$stateDir = Join-Path $runDir "state"
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null

$statusFile = Join-Path $stateDir "status.txt"
$briefFile = Join-Path $stateDir "consolidated_brief.md"
$decisionFile = Join-Path $stateDir "decision.json"

function Send-ExecutiveBrief([string]$Ack, [string]$Status, [string]$Gov, [string]$Decision) {
    $brief = @"
🫡 **Acknowledgment:** $Ack
📊 **Status Update:** $Status
🛡️ **Governance:** $Gov
❓ **Decision Point:** $Decision
"@
    # Write to status.txt for Dashboard polling
    $brief | Set-Content -Path $statusFile -Force
    # Also push to chat history as Deputy
    python "$RepoRoot\scripts\chat_bridge.py" "$runDir" "Deputy" "$brief"
    Write-Host $brief -ForegroundColor Cyan
}

function Check-For-Pivot {
    $res = python "$RepoRoot\scripts\chat_bridge.py" check "$runDir"
    if ($res) {
        $instr = $res | ConvertFrom-Json
        $content = $instr.content
        
        # Immediate Manager Intercept
        $interceptMsg = "Commander, I am pausing the Specialists to incorporate your strategic pivot: '$content'. Standing by for further instructions."
        python "$RepoRoot\scripts\chat_bridge.py" "$runDir" "Deputy" "$interceptMsg"
        
        Start-Sleep -Seconds 3
        return $content
    }
    return $null
}

# 1. Start Operations
Send-ExecutiveBrief `
    -Ack "Confirmed mission: $Prompt" `
    -Status "Allocating resources and initializing the specialized triad." `
    -Gov "Preparing the consolidated brief for your review." `
    -Decision "Should I prioritize speed or depth for this initial research phase?"

# 2. Architect Phase
Check-For-Pivot | Out-Null
Send-ExecutiveBrief `
    -Ack "Commander's intent received." `
    -Status "The Architect is drafting the strategic roadmap." `
    -Gov "Technical plan is being finalized." `
    -Decision "Do you want a full SWOT analysis included in the brief?"

# Simulate Architect Output
$plan = @{
    objective = $Prompt
    steps = @("Analyze current state", "Implement optimization", "Verify with tests")
} | ConvertTo-Json
$plan | Set-Content -Path (Join-Path $stateDir "plan.json") -Force

# Present Consolidated Brief for Governance
$briefMd = @"
# 📋 Consolidated Brief: Operation Market Dominance
**Objective:** $Prompt

## 🗺️ Resource Allocation
- **Architect:** Mapping competitive landscape.
- **Engineer:** Preparing scraping protocols.
- **Tester:** Validating data integrity.

## ⚠️ Risk Assessment
- **High:** Anti-bot detection on target directories.
- **Medium:** Inconsistent menu formats across sources.

**Awaiting Commander's Approval to PROCEED.**
"@
$briefMd | Set-Content -Path $briefFile -Force

# Call Governance Gate
Send-ExecutiveBrief `
    -Ack "Strategic roadmap complete." `
    -Status "Standing by for your authorization." `
    -Gov "Consolidated Brief is ready for review." `
    -Decision "Shall we proceed with this allocation?"

python "$RepoRoot\scripts\governance_gate.py" "$runDir"

# 3. Specialist Execution Loop
$attempts = 0
$maxAttempts = 3
$success = $false

while ($attempts -lt $maxAttempts -and -not $success) {
    $attempts++
    Check-For-Pivot | Out-Null
    
    Send-ExecutiveBrief `
        -Ack "Operational authorization confirmed." `
        -Status "The Engineer is executing implementation turn $attempts." `
        -Gov "Monitoring for regressions." `
        -Decision "Do you wish to see a partial preview of the data now?"

    # Simulate implementation and test failure
    if ($attempts -lt 2) {
        Check-For-Pivot | Out-Null
        "TEST FAILURE: Proxy timeout." | Set-Content -Path (Join-Path $stateDir "feedback.md") -Force
        Send-ExecutiveBrief `
            -Ack "Internal conflict detected." `
            -Status "Tester identified a failure. Chief of Staff is mediating between Engineer and Tester." `
            -Gov "No action required from Commander (Internal Resolution $attempts/3)." `
            -Decision "Should I rotate to a more aggressive proxy set if this fails again?"
        Start-Sleep -Seconds 5
    } else {
        Check-For-Pivot | Out-Null
        "SUCCESS: Market data captured and cleaned." | Set-Content -Path (Join-Path $stateDir "feedback.md") -Force
        $success = $true
    }
}

if ($success) {
    Send-ExecutiveBrief `
        -Ack "Mission Accomplished." `
        -Status "Specialists have completed all tasks successfully." `
        -Gov "Final data package is ready for your inspection." `
        -Decision "Ready for the next operation, Commander?"
} else {
    Send-ExecutiveBrief `
        -Ack "Operational Failure Escalated." `
        -Status "Specialists reached maximum retries without resolution." `
        -Gov "Manual intervention required." `
        -Decision "Would you like to take manual control of the shell?"
}
