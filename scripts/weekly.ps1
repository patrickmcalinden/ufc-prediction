<#
.SYNOPSIS
  Wrapper that Task Scheduler invokes to run the weekly UFC pipeline.

.DESCRIPTION
  Two things this does that `python -m pipeline.weekly` can't do for itself:

    1. Makes sure Docker Desktop is running, since Postgres lives in the
       ufc_postgres container. A task that fires just after the machine wakes
       can easily beat Docker to the punch; weekly.py then waits for the DB.
    2. Normalises the working directory and exit code so Task Scheduler's
       "Last Run Result" column actually means something.

.PARAMETER Mode
  grade  - reconcile + grade completed events only  (Sunday night)
  lock   - lock picks for the next upcoming event    (Friday night)
  full   - both halves in one run

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\weekly.ps1 -Mode lock
#>
[CmdletBinding()]
param(
    [ValidateSet('grade', 'lock', 'full')]
    [string]$Mode = 'full',

    [int]$LookbackDays = 8,

    # Passed straight through to pipeline.weekly (e.g. -Extra '--no-merge').
    [string[]]$Extra = @()
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Error "Virtualenv python not found at $python"
    exit 3
}

function Ensure-Docker {
    # `docker ps` is the honest readiness check — the Docker Desktop process
    # can be up while the engine is still starting.
    for ($i = 0; $i -lt 30; $i++) {
        docker ps --format '{{.Names}}' 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return $true }

        if ($i -eq 0) {
            $exe = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
            if (Test-Path $exe) {
                Write-Host 'Docker engine not responding - starting Docker Desktop...'
                Start-Process -FilePath $exe | Out-Null
            }
            else {
                Write-Warning "Docker Desktop not found at $exe"
            }
        }
        Start-Sleep -Seconds 10
    }
    return $false
}

if (-not (Ensure-Docker)) {
    Write-Error 'Docker engine never came up - aborting.'
    exit 4
}

# The container is restart:always, but a manual `docker stop` would leave it down.
$running = docker ps --filter 'name=ufc_postgres' --format '{{.Names}}'
if (-not $running) {
    Write-Host 'Starting ufc_postgres container...'
    docker start ufc_postgres | Out-Null
}

$modeFlags = switch ($Mode) {
    'grade' { @('--no-lock') }
    'lock'  { @('--no-grade') }
    'full'  { @() }
}

$argList = @('-m', 'pipeline.weekly', '--lookback-days', "$LookbackDays") + $modeFlags + $Extra
Write-Host "> $python $($argList -join ' ')"
& $python @argList
exit $LASTEXITCODE
