Set-StrictMode -Version Latest

# Common helpers shared across Gemini OP PowerShell scripts.
# Dot-source from scripts, e.g.:
#   . (Join-Path $PSScriptRoot 'lib\common.ps1')

# Script-scoped log file path (optional). Initialized via Initialize-GeminiLogging.
$script:GeminiLogFile = $null

function Protect-GeminiSensitiveText {
  <#
  .SYNOPSIS
  Redacts common secret patterns from text intended for logs.

  .DESCRIPTION
  Applies conservative redaction for common API keys/tokens/passwords.
  This is a best-effort sanitizer and should not be treated as the only
  security boundary.

  .PARAMETER Text
  Input text.

  .EXAMPLE
  Protect-GeminiSensitiveText -Text 'Authorization: Bearer sk-...'
  #>
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
    [string]$Text
  )

  $t = $Text

  # OpenAI / generic "sk-" style keys
  $t = [regex]::Replace($t, '(?i)\bsk-[A-Za-z0-9]{10,}\b', 'sk-REDACTED')

  # GitHub fine-grained / classic PAT patterns
  $t = [regex]::Replace($t, '(?i)\bgithub_pat_[A-Za-z0-9_]{10,}\b', 'github_pat_REDACTED')
  $t = [regex]::Replace($t, '(?i)\bgh[pous]_[A-Za-z0-9]{20,}\b', 'gh_REDACTED')

  # Notion tokens often start with "ntn_" in some setups
  $t = [regex]::Replace($t, '(?i)\bntn_[A-Za-z0-9]{10,}\b', 'ntn_REDACTED')

  # Generic key/value secrets
  $t = [regex]::Replace($t, '(?i)(api[_-]?key\s*[:=]\s*)([^\s" '']+)', '$1REDACTED')
  $t = [regex]::Replace($t, '(?i)(token\s*[:=]\s*)([^\s" '']+)', '$1REDACTED')
  $t = [regex]::Replace($t, '(?i)(password\s*[:=]\s*)([^\s" '']+)', '$1REDACTED')

  # Authorization headers
  $t = [regex]::Replace($t, '(?i)(Authorization\s*:\s*Bearer\s+)([^\s]+)', '$1REDACTED')

  return $t
}

function Initialize-GeminiLogging {
  <#
  .SYNOPSIS
  Initializes file logging for the current script.

  .PARAMETER LogDirectory
  Directory that will contain the log file. The directory is created if missing.

  .PARAMETER LogFileName
  Log filename (default: Gemini.log).

  .EXAMPLE
  Initialize-GeminiLogging -LogDirectory $RunDir -LogFileName 'triad_orchestrator.log'
  #>
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)]
    [string]$LogDirectory,

    [Parameter()]
    [string]$LogFileName = 'Gemini.log'
  )

  if ([string]::IsNullOrWhiteSpace($LogDirectory)) {
    throw 'LogDirectory is required.'
  }

  $dir = (Resolve-Path -LiteralPath $LogDirectory -ErrorAction SilentlyContinue)
  if (-not $dir) {
    New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
    $dir = Resolve-Path -LiteralPath $LogDirectory
  }

  $script:GeminiLogFile = Join-Path $dir.Path $LogFileName
  if (-not (Test-Path -LiteralPath $script:GeminiLogFile)) {
    New-Item -ItemType File -Force -Path $script:GeminiLogFile | Out-Null
  }
}

function Write-GeminiLog {
  <#
  .SYNOPSIS
  Writes a structured log line to console and (if configured) to a log file.

  .DESCRIPTION
  Log lines are timestamped and sanitized via Protect-GeminiSensitiveText.

  .PARAMETER Message
  The log message.

  .PARAMETER Level
  INFO, WARN, ERROR, or DEBUG.

  .PARAMETER NoConsole
  If set, do not write to console.

  .PARAMETER NoFile
  If set, do not append to log file.

  .EXAMPLE
  Write-GeminiLog -Level INFO -Message 'Starting run'
  #>
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)]
    [string]$Message,

    [Parameter()]
    [ValidateSet('INFO', 'WARN', 'ERROR', 'DEBUG')]
    [string]$Level = 'INFO',

    [Parameter()]
    [switch]$NoConsole,

    [Parameter()]
    [switch]$NoFile
  )

  $ts = Get-Date -Format o
  $safe = Protect-GeminiSensitiveText -Text $Message
  $line = "[$ts] [$Level] $safe"

  if (-not $NoConsole) {
    if ($Level -eq 'ERROR') {
      Write-Host $line -ForegroundColor Red
    } elseif ($Level -eq 'WARN') {
      Write-Host $line -ForegroundColor Yellow
    } else {
      Write-Host $line
    }
  }

  if (-not $NoFile -and $script:GeminiLogFile) {
    try {
      Add-Content -LiteralPath $script:GeminiLogFile -Value $line -Encoding UTF8
    } catch {
      # Avoid recursive logging if file system is unavailable.
      Write-Host "[$ts] [WARN] Failed to write log file: $($script:GeminiLogFile)" -ForegroundColor Yellow
    }
  }
}

function Assert-GeminiCommand {
  <#
  .SYNOPSIS
  Ensures a command exists in PATH.

  .PARAMETER CommandName
  The command to check.

  .EXAMPLE
  Assert-GeminiCommand -CommandName 'git'
  #>
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)]
    [string]$CommandName
  )

  $cmd = Get-Command $CommandName -ErrorAction SilentlyContinue
  if (-not $cmd) {
    throw "Required command not found in PATH: $CommandName"
  }
}

function Wait-GeminiGitLockClear {
  <#
  .SYNOPSIS
  Waits for common git lock files to clear.

  .DESCRIPTION
  Detects .git/index.lock and related lock files that can occur during
  concurrent git operations or crashes.

  .PARAMETER RepoRoot
  Path to the git repository root.

  .PARAMETER TimeoutSec
  Maximum time to wait for locks to clear.

  .PARAMETER PollSec
  Poll interval.

  .EXAMPLE
  Wait-GeminiGitLockClear -RepoRoot $RepoRoot -TimeoutSec 120
  #>
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [Parameter()]
    [ValidateRange(1, 3600)]
    [int]$TimeoutSec = 120,

    [Parameter()]
    [ValidateRange(1, 30)]
    [int]$PollSec = 2
  )

  $gitDir = Join-Path $RepoRoot '.git'
  if (-not (Test-Path -LiteralPath $gitDir)) {
    return
  }

  $lockPaths = @(
    (Join-Path $gitDir 'index.lock'),
    (Join-Path $gitDir 'HEAD.lock'),
    (Join-Path $gitDir 'packed-refs.lock'),
    (Join-Path $gitDir 'config.lock'),
    (Join-Path $gitDir 'shallow.lock')
  )

  $start = Get-Date
  while ($true) {
    $active = @($lockPaths | Where-Object { Test-Path -LiteralPath $_ })
    if ($active.Count -eq 0) {
      return
    }

    $elapsed = (New-TimeSpan -Start $start -End (Get-Date)).TotalSeconds
    if ($elapsed -ge $TimeoutSec) {
      $msg = "git lock(s) still present after ${TimeoutSec}s:`n" + ($active -join "`n")
      throw $msg
    }

    Write-GeminiLog -Level WARN -Message ("git lock detected; waiting (elapsed_s={0})" -f [int]$elapsed)
    Start-Sleep -Seconds $PollSec
  }
}

function Invoke-GeminiExternalCommand {
  <#
  .SYNOPSIS
  Runs an external command with optional timeout and captured stdout/stderr.

  .PARAMETER FilePath
  Executable or command name.

  .PARAMETER ArgumentList
  Argument list.

  .PARAMETER WorkingDirectory
  Working directory.

  .PARAMETER TimeoutSec
  If > 0, kill the process if it exceeds this runtime.

  .PARAMETER ThrowOnNonZero
  If set, throws when ExitCode is non-zero or timed out.

  .PARAMETER SuppressArgLogging
  If set, do not include arguments in log lines.

  .EXAMPLE
  Invoke-GeminiExternalCommand -FilePath 'python' -ArgumentList @('--version') -TimeoutSec 10
  #>
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    [Parameter()]
    [string[]]$ArgumentList = @(),

    [Parameter()]
    [string]$WorkingDirectory = $null,

    [Parameter()]
    [ValidateRange(0, 86400)]
    [int]$TimeoutSec = 0,

    [Parameter()]
    [switch]$ThrowOnNonZero,

    [Parameter()]
    [switch]$SuppressArgLogging
  )

  $stdoutTmp = [System.IO.Path]::GetTempFileName()
  $stderrTmp = [System.IO.Path]::GetTempFileName()

  $startInfo = @{
    FilePath               = $FilePath
    ArgumentList           = $ArgumentList
    PassThru               = $true
    NoNewWindow            = $true
    RedirectStandardOutput = $stdoutTmp
    RedirectStandardError  = $stderrTmp
  }
  if ($WorkingDirectory) {
    $startInfo.WorkingDirectory = $WorkingDirectory
  }

  $displayArgs = ''
  if (-not $SuppressArgLogging -and $ArgumentList -and $ArgumentList.Count -gt 0) {
    $displayArgs = ' ' + (Protect-GeminiSensitiveText -Text ($ArgumentList -join ' '))
  }

  Write-GeminiLog -Level DEBUG -Message ("exec: {0}{1}" -f $FilePath, $displayArgs)

  $proc = $null
  $timedOut = $false
  try {
    $proc = Start-Process @startInfo
    if ($TimeoutSec -gt 0) {
      $null = Wait-Process -Id $proc.Id -Timeout $TimeoutSec -ErrorAction SilentlyContinue
      if (-not $proc.HasExited) {
        $timedOut = $true
        try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch { }
      }
    } else {
      $proc.WaitForExit()
    }
  } finally {
    if ($proc -and -not $proc.HasExited -and $proc.Id -ne $PID) {
      try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch { }
    }
  }

  $stdout = ''
  $stderr = ''
  try { $stdout = (Get-Content -LiteralPath $stdoutTmp -Raw -ErrorAction SilentlyContinue) } catch { }
  try { $stderr = (Get-Content -LiteralPath $stderrTmp -Raw -ErrorAction SilentlyContinue) } catch { }

  try { Remove-Item -LiteralPath $stdoutTmp -Force -ErrorAction SilentlyContinue } catch { }
  try { Remove-Item -LiteralPath $stderrTmp -Force -ErrorAction SilentlyContinue } catch { }

  $exitCode = if ($proc) { $proc.ExitCode } else { 1 }
  if ($timedOut) { $exitCode = 124 }

  $result = [pscustomobject]@{
    FilePath = $FilePath
    Args     = $ArgumentList
    ExitCode = $exitCode
    TimedOut = $timedOut
    StdOut   = $stdout
    StdErr   = $stderr
  }

  if ($ThrowOnNonZero -and ($timedOut -or $exitCode -ne 0)) {
    $errMsg = "command failed: $FilePath (exit=$exitCode timed_out=$timedOut)"
    if (-not [string]::IsNullOrWhiteSpace($stderr)) {
      $errMsg += "`n" + (Protect-GeminiSensitiveText -Text ($stderr.Trim()))
    }
    throw $errMsg
  }

  return $result
}

function Invoke-GeminiGit {
  <#
  .SYNOPSIS
  Runs a git command with retries, lock handling, and an optional timeout.

  .PARAMETER RepoRoot
  Git repo root.

  .PARAMETER Args
  Git arguments (excluding -C).

  .PARAMETER TimeoutSec
  Per-attempt timeout.

  .PARAMETER Retries
  Number of retries for transient failures.

  .EXAMPLE
  Invoke-GeminiGit -RepoRoot $RepoRoot -Args @('status','--porcelain=v1')
  #>
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [Parameter(Mandatory = $true)]
    [string[]]$Args,

    [Parameter()]
    [ValidateRange(1, 3600)]
    [int]$TimeoutSec = 300,

    [Parameter()]
    [ValidateRange(0, 10)]
    [int]$Retries = 2,

    [Parameter()]
    [ValidateRange(1, 30)]
    [int]$RetryDelaySec = 3
  )

  Assert-GeminiCommand -CommandName 'git'

  $attempt = 0
  while ($true) {
    $attempt += 1
    try {
      Wait-GeminiGitLockClear -RepoRoot $RepoRoot -TimeoutSec 120
      $gitArgs = @('-C', $RepoRoot) + $Args
      $res = Invoke-GeminiExternalCommand -FilePath 'git' -ArgumentList $gitArgs -WorkingDirectory $RepoRoot -TimeoutSec $TimeoutSec
      if ($res.ExitCode -eq 0 -and -not $res.TimedOut) {
        return $res
      }

      $stderr = ($res.StdErr | Out-String).Trim()
      $isLock = $stderr -match '(?i)index\.lock|Another git process seems to be running'
      $isNetwork = $stderr -match '(?i)Could not resolve host|Failed to connect|Connection timed out|TLS|SSL|The requested URL returned error'

      if ($attempt -le ($Retries + 1) -and ($isLock -or $isNetwork -or $res.TimedOut)) {
        Write-GeminiLog -Level WARN -Message ("git transient failure (attempt={0}/{1}) cmd=git {2}" -f $attempt, ($Retries + 1), ($Args -join ' '))
        Start-Sleep -Seconds $RetryDelaySec
        continue
      }

      $msg = "git failed: git -C $RepoRoot $($Args -join ' ') (exit=$($res.ExitCode) timed_out=$($res.TimedOut))"
      if (-not [string]::IsNullOrWhiteSpace($stderr)) {
        $msg += "`n" + (Protect-GeminiSensitiveText -Text $stderr)
      }
      throw $msg
    } catch {
      if ($attempt -le ($Retries + 1)) {
        $m = $_.Exception.Message
        if ($m -match '(?i)index\.lock|Connection timed out|Could not resolve host|Failed to connect|timed_out=True|timed_out=true') {
          Write-GeminiLog -Level WARN -Message ("git retry after error (attempt={0}/{1}): {2}" -f $attempt, ($Retries + 1), $m)
          Start-Sleep -Seconds $RetryDelaySec
          continue
        }
      }
      throw
    }
  }
}
