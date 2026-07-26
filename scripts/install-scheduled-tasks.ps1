<#
.SYNOPSIS
  Register (or remove) the Windows Task Scheduler entries that keep the site
  up to date without anyone remembering to run anything.

.DESCRIPTION
  Creates two tasks under the \UFC Predictor\ folder:

    Lock picks    - Friday  21:00, `weekly.ps1 -Mode lock`
                    Late enough that Friday weigh-in withdrawals are already
                    reflected on ESPN, so we don't lock picks for fights that
                    never make it to Saturday. Early enough that a failure
                    still leaves Saturday morning to fix by hand.

    Grade results - Sunday  21:00, `weekly.ps1 -Mode grade`
                    Grades Saturday's card the next day rather than waiting
                    for the following Friday.

  Both tasks:
    - run only when this user is logged on (Docker Desktop needs the
      interactive session, and this avoids storing a password)
    - wake the machine if it's asleep
    - run as soon as possible after a missed start, so a weekend away costs
      you a late update instead of a skipped one
    - give up after 3 hours

.PARAMETER Remove
  Unregister both tasks instead of creating them.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\install-scheduled-tasks.ps1
  powershell -ExecutionPolicy Bypass -File scripts\install-scheduled-tasks.ps1 -Remove
#>
[CmdletBinding()]
param(
    [switch]$Remove,
    [string]$LockTime = '21:00',
    [string]$GradeTime = '21:00',
    [string]$TaskPath = '\UFC Predictor\'
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$wrapper = Join-Path $repo 'scripts\weekly.ps1'

if (-not (Test-Path $wrapper)) {
    Write-Error "Wrapper script not found at $wrapper"
    exit 1
}

$tasks = @(
    @{ Name = 'Lock picks';    Mode = 'lock';  Day = 'Friday'; Time = $LockTime
       Desc = 'Scrape the next UFC card, train models, lock predictions, export site JSON, open+merge a PR (which redeploys GitHub Pages).' }
    @{ Name = 'Grade results'; Mode = 'grade'; Day = 'Sunday'; Time = $GradeTime
       Desc = 'Reconcile completed events, refresh stats, rebuild Elo, grade locked picks, export site JSON, open+merge a PR.' }
)

foreach ($t in $tasks) {
    $existing = Get-ScheduledTask -TaskName $t.Name -TaskPath $TaskPath -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $t.Name -TaskPath $TaskPath -Confirm:$false
        Write-Host "Removed existing task: $TaskPath$($t.Name)"
    }
    if ($Remove) { continue }

    $action = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$wrapper`" -Mode $($t.Mode)" `
        -WorkingDirectory $repo

    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $t.Day -At $t.Time

    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -WakeToRun `
        -RunOnlyIfNetworkAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
        -MultipleInstances IgnoreNew

    # Interactive so Docker Desktop can be started in this user's session.
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

    Register-ScheduledTask -TaskName $t.Name -TaskPath $TaskPath `
        -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
        -Description $t.Desc | Out-Null

    Write-Host "Registered: $TaskPath$($t.Name)  ->  $($t.Day) $($t.Time)  (-Mode $($t.Mode))"
}

if ($Remove) {
    Write-Host 'Done - both tasks removed.'
}
else {
    Write-Host ''
    Write-Host 'Verify with:'
    Write-Host "  Get-ScheduledTask -TaskPath '$TaskPath' | Select-Object TaskName,State"
    Write-Host "  Get-ScheduledTaskInfo -TaskPath '$TaskPath' -TaskName 'Lock picks'"
    Write-Host 'Dry-run one now (this really does open and merge a PR):'
    Write-Host "  Start-ScheduledTask -TaskPath '$TaskPath' -TaskName 'Lock picks'"
}
