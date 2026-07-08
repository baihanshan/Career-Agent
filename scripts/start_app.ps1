param(
    [Alias("h")]
    [switch]$Help,
    [switch]$NoBrowser,
    [string]$CondaEnv = $(if ($env:CONDA_ENV) { $env:CONDA_ENV } else { "carrer_agent" }),
    [string]$PythonVersion = $(if ($env:PYTHON_VERSION) { $env:PYTHON_VERSION } else { "3.11" }),
    [string]$HostName = $(if ($env:HOST) { $env:HOST } else { "127.0.0.1" }),
    [int]$BackendPort = $(if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8000 }),
    [int]$FrontendPort = $(if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 3000 })
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$FrontendDir = Join-Path $RootDir "frontend"
$LogDir = Join-Path $RootDir ".local\logs"
$BackendUrl = "http://${HostName}:${BackendPort}"
$FrontendUrl = "http://${HostName}:${FrontendPort}"
$OpenBrowser = -not $NoBrowser -and $env:OPEN_BROWSER -ne "0"

$BackendProcess = $null
$FrontendProcess = $null

function Show-Usage {
    Write-Host "CareerPilot Agent local launcher"
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\start_app.ps1 [-NoBrowser]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -NoBrowser"
    Write-Host "  -CondaEnv carrer_agent"
    Write-Host "  -BackendPort 8000"
    Write-Host "  -FrontendPort 3000"
    Write-Host ""
    Write-Host "The launcher starts the FastAPI backend and Next.js frontend, then opens:"
    Write-Host "  $FrontendUrl"
}

function Find-Conda {
    $command = Get-Command conda.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path $env:USERPROFILE "miniforge3\Scripts\conda.exe")
        (Join-Path $env:USERPROFILE "miniconda3\Scripts\conda.exe")
        (Join-Path $env:USERPROFILE "anaconda3\Scripts\conda.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Require-Command {
    param(
        [string]$Name,
        [string]$InstallHint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Name`n$InstallHint"
    }
}

function Test-PortInUse {
    param([int]$Port)

    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

function Test-UrlOk {
    param([string]$Url)

    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Show-LogTail {
    param(
        [string]$LogFile,
        [int]$LineCount = 80
    )

    if (-not (Test-Path $LogFile)) {
        Write-Host "Log file does not exist yet: $LogFile"
        return
    }

    Write-Host ""
    Write-Host "Last $LineCount log lines from ${LogFile}:"
    Write-Host "----------------------------------------"
    Get-Content -Path $LogFile -Tail $LineCount
    Write-Host "----------------------------------------"
}

function Show-ProcessLogs {
    param(
        [string[]]$LogFiles,
        [int]$LineCount = 80
    )

    foreach ($logFile in $LogFiles) {
        Show-LogTail $logFile $LineCount
    }
}

function Wait-ForUrl {
    param(
        [string]$Url,
        [string]$Label,
        [int]$Attempts = 90,
        [string[]]$LogFiles = @(),
        [System.Diagnostics.Process]$Process = $null
    )

    for ($i = 0; $i -lt $Attempts; $i++) {
        if (Test-UrlOk $Url) {
            return
        }

        if ($null -ne $Process) {
            $Process.Refresh()
            if ($Process.HasExited) {
                if ($LogFiles.Count -gt 0) {
                    Show-ProcessLogs $LogFiles
                }
                throw "$Label process exited before $Url became ready. Exit code: $($Process.ExitCode)"
            }
        }

        Start-Sleep -Seconds 1
    }

    if ($LogFiles.Count -gt 0) {
        Show-ProcessLogs $LogFiles
    }
    throw "$Label did not become ready at $Url"
}

function Test-BackendDependencies {
    param([string]$CondaBin)

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Missing Python packages write a traceback to stderr. In Windows PowerShell,
        # that can become NativeCommandError and stop the launcher before install runs.
        $ErrorActionPreference = "Continue"
        $probeCommand = "import fastapi, uvicorn"
        & $CondaBin run -n $CondaEnv python -c $probeCommand *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

function Ensure-BackendEnvironment {
    param([string]$CondaBin)

    $envList = & $CondaBin env list
    $envExists = $false
    foreach ($line in $envList) {
        if ($line -match "^\s*\*?\s*$([regex]::Escape($CondaEnv))\s+") {
            $envExists = $true
            break
        }
    }

    if (-not $envExists) {
        Write-Host "Creating conda environment: $CondaEnv"
        & $CondaBin create -n $CondaEnv python=$PythonVersion -y
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create conda environment: $CondaEnv"
        }
    }

    if (-not (Test-BackendDependencies $CondaBin)) {
        Write-Host "Installing backend dependencies into conda environment: $CondaEnv"
        & $CondaBin run -n $CondaEnv pip install -r (Join-Path $RootDir "requirements-dev.txt")
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install backend dependencies."
        }
    }
}

function Ensure-FrontendEnvironment {
    if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
        Write-Host "Installing frontend dependencies..."
        Push-Location $FrontendDir
        try {
            npm install
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to install frontend dependencies."
            }
        }
        finally {
            Pop-Location
        }
    }
}

function Start-Backend {
    param([string]$CondaBin)

    $stdoutLogFile = Join-Path $LogDir "backend.out.log"
    $stderrLogFile = Join-Path $LogDir "backend.err.log"

    if (Test-UrlOk "$BackendUrl/health") {
        Write-Host "Backend is already running at $BackendUrl"
        return
    }

    if (Test-PortInUse $BackendPort) {
        throw "Port $BackendPort is already in use, but $BackendUrl/health is not healthy. Stop that process or set -BackendPort."
    }

    Write-Host "Starting backend at $BackendUrl"
    $arguments = @(
        "run", "-n", $CondaEnv,
        "uvicorn", "backend.app.main:app",
        "--reload",
        "--log-level", "debug",
        "--host", $HostName,
        "--port", "$BackendPort"
    )
    $script:BackendProcess = Start-Process `
        -FilePath $CondaBin `
        -ArgumentList $arguments `
        -WorkingDirectory $RootDir `
        -RedirectStandardOutput $stdoutLogFile `
        -RedirectStandardError $stderrLogFile `
        -PassThru `
        -WindowStyle Hidden

    Wait-ForUrl "$BackendUrl/health" "Backend" 120 @($stdoutLogFile, $stderrLogFile) $script:BackendProcess
}

function Start-Frontend {
    $logFile = Join-Path $LogDir "frontend.log"

    if (Test-UrlOk $FrontendUrl) {
        Write-Host "Frontend is already running at $FrontendUrl"
        return
    }

    if (Test-PortInUse $FrontendPort) {
        throw "Port $FrontendPort is already in use, but $FrontendUrl is not reachable. Stop that process or set -FrontendPort."
    }

    Write-Host "Starting frontend at $FrontendUrl"
    $command = "set `"NEXT_PUBLIC_API_BASE_URL=$BackendUrl`" && cd /d `"$FrontendDir`" && npm run dev -- -H $HostName -p $FrontendPort >> `"$logFile`" 2>&1"
    $script:FrontendProcess = Start-Process `
        -FilePath "cmd.exe" `
        -ArgumentList @("/c", $command) `
        -WorkingDirectory $FrontendDir `
        -PassThru `
        -WindowStyle Hidden

    Wait-ForUrl $FrontendUrl "Frontend" 120 @($logFile) $script:FrontendProcess
}

function Stop-StartedProcesses {
    foreach ($process in @($script:FrontendProcess, $script:BackendProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            try {
                taskkill /PID $process.Id /T /F *> $null
            }
            catch {
            }
        }
    }
}

try {
    if ($Help) {
        Show-Usage
        exit 0
    }

    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    Require-Command "npm.cmd" "Install Node.js and npm, then run this launcher again."

    $condaBin = Find-Conda
    if (-not $condaBin) {
        throw "Could not find conda. Install Miniforge, Miniconda, or Anaconda, then run this launcher again."
    }

    Ensure-BackendEnvironment $condaBin
    Ensure-FrontendEnvironment
    Start-Backend $condaBin
    Start-Frontend

    if ($OpenBrowser) {
        Start-Process $FrontendUrl
    }

    Write-Host ""
    Write-Host "CareerPilot Agent is running:"
    Write-Host "  Frontend: $FrontendUrl"
    Write-Host "  Backend:  $BackendUrl"
    Write-Host ""
    Write-Host "Logs:"
    Write-Host "  $(Join-Path $LogDir "backend.out.log")"
    Write-Host "  $(Join-Path $LogDir "backend.err.log")"
    Write-Host "  $(Join-Path $LogDir "frontend.log")"
    Write-Host ""
    Write-Host "Press Ctrl+C in this terminal to stop services started by this launcher."

    while ($true) {
        Start-Sleep -Seconds 2
    }
}
finally {
    Stop-StartedProcesses
}
