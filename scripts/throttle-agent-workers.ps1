param(
  [Parameter(Mandatory = $true)]
  [string]$RunDir,

  [int]$MaxWorkers = 5,
  [double]$TargetCpuPct = 75,
  [int]$PollSeconds = 5,
  [int]$DurationMinutes = 120,
  [ValidateSet('BelowNormal','Idle')]
  [string]$Priority = 'BelowNormal'
)

$ErrorActionPreference = 'Continue'

function Get-RunWorkerShells {
  $esc = [regex]::Escape($RunDir)
  Get-CimInstance Win32_Process |
    Where-Object {
      ($_.Name -match 'pwsh.exe|powershell.exe') -and (
        $_.CommandLine -match $esc -or
        $_.CommandLine -match ('output-last-message\s+' + $esc)
      )
    } |
    Select-Object ProcessId, CreationDate, Name, CommandLine
}

function Set-WorkerPriority([int]$ProcessId, [string]$Class) {
  try {
    $p = Get-Process -Id $ProcessId -ErrorAction Stop
    if ($p.PriorityClass.ToString() -ne $Class) {
      $p.PriorityClass = $Class
    }
  } catch {
  }
}

function Stop-Worker([int]$ProcessId) {
  try {
    Stop-Process -Id $ProcessId -Force -ErrorAction Stop
    return $true
  } catch {
    return $false
  }
}

function Get-CpuPct {
  try {
    return [double](Get-Counter '\Processor(_Total)\% Processor Time').CounterSamples.CookedValue
  } catch {
    return 0
  }
}

$start = Get-Date
$end = $start.AddMinutes($DurationMinutes)
Write-Host "Throttle started. run_dir=$RunDir max_workers=$MaxWorkers target_cpu=$TargetCpuPct priority=$Priority"

while ((Get-Date) -lt $end) {
  $cpu = Get-CpuPct
  $workers = @(Get-RunWorkerShells | Sort-Object CreationDate)
  $count = $workers.Count

  foreach ($w in $workers) {
    Set-WorkerPriority -ProcessId $w.ProcessId -Class $Priority
  }

  if ($count -gt $MaxWorkers -or $cpu -gt $TargetCpuPct) {
    $overByCount = [Math]::Max(0, $count - $MaxWorkers)
    $extra = if ($cpu -gt $TargetCpuPct) { 1 } else { 0 }
    $toStop = [Math]::Min($count, $overByCount + $extra)
    if ($toStop -gt 0) {
      # Stop newest workers first to preserve earliest runs.
      $victims = $workers | Sort-Object CreationDate -Descending | Select-Object -First $toStop
      foreach ($v in $victims) {
        $ok = Stop-Worker -ProcessId $v.ProcessId
        if ($ok) {
          Write-Host ("[{0}] throttled pid={1} cpu={2:n1} workers={3}" -f (Get-Date -Format o), $v.ProcessId, $cpu, $count)
        }
      }
    }
  }

  Write-Host ("[{0}] cpu={1:n1}% workers={2}" -f (Get-Date -Format o), $cpu, $count)
  Start-Sleep -Seconds $PollSeconds
}

Write-Host "Throttle finished."
