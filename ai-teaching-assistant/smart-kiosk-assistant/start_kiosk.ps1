# =============================================================================
# start_kiosk.ps1
# Smart Kiosk Assistant - Windows 11 Service Launcher
#
# Features:
# - Starts all 5 services in parallel
# - Monitors service health
# - Auto-restart on failure
# - Unified console logging
# - Graceful shutdown (Ctrl+C)
# - Auto-opens browser to Gradio UI
#
# Usage: powershell -ExecutionPolicy Bypass -File start_kiosk.ps1
# =============================================================================

param(
    [switch]$Silent = $false,  # Suppress extra output
    [switch]$NoBrowser = $false,  # Don't auto-open browser
    [int]$StartupTimeoutSeconds = 600  # First-run model warmup can take several minutes
)

$ErrorActionPreference = "Stop"
$WarningPreference = "SilentlyContinue"

# Global state
$Global:ProcessJobs = @{}
$Global:ServiceHealth = @{}
$Global:ShutdownInProgress = $false

# Color output
function Write-Header {
    param([string]$Message)
    Write-Host "`n" -ForegroundColor White
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "=" * 70 -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    if (-not $Silent) {
        Write-Host "[*] $Message" -ForegroundColor Yellow
    }
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Red
}

function Write-Log {
    param([string]$Message, [string]$Service)
    $Timestamp = (Get-Date).ToString("HH:mm:ss")
    $Color = "White"
    
    switch ($Service) {
        "audio-analyzer" { $Color = "Magenta" }
        "text-to-speech" { $Color = "Yellow" }
        "rag-service" { $Color = "Cyan" }
        "kiosk-core" { $Color = "Green" }
        "kiosk-ui" { $Color = "Blue" }
        "launcher" { $Color = "White" }
    }
    
    Write-Host "[$Timestamp] [$Service] $Message" -ForegroundColor $Color
}

function Write-Step {
    param([string]$Message)
    Write-Host "`n→ $Message" -ForegroundColor Cyan
}

# Get root directory and service paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir  # Go up to voice-enabled-interactions root
$KioskDir = $ScriptDir  # smart-kiosk-assistant is the kiosk directory
$EdgeAIDir = Join-Path $RootDir "edge-ai-libraries"

# Load .env file
function Load-Env {
    $EnvFile = Join-Path $ScriptDir ".env"
    if (Test-Path $EnvFile) {
        Get-Content $EnvFile | ForEach-Object {
            if ($_ -match "^([^=]+)=(.*)$") {
                [Environment]::SetEnvironmentVariable($matches[1], $matches[2])
            }
        }
        Write-Success "Environment variables loaded from .env"
    }
    else {
        Write-Error-Custom ".env file not found at: $EnvFile"
        Write-Info "Run setup_windows.ps1 first to create it"
        exit 1
    }
}

# Service definitions
$Services = @(
    @{
        Name = "metrics-collector"
        Port = 9000
        Path = "$KioskDir\kiosk_core\metrics-collector\windows"
        MainFile = "metrics_collector.ps1"
        HealthUrl = "http://127.0.0.1:9000/health"
        Description = "System Metrics Collector"
        Runtime = "powershell"
    },
    @{
        Name = "text-to-speech"
        Port = 8011
        Path = "$EdgeAIDir\microservices\text-to-speech"
        MainFile = "main.py"
        HealthUrl = "http://127.0.0.1:8011/health"
        Description = "Text-to-Speech Synthesis"
    },
    @{
        Name = "audio-analyzer"
        Port = 8010
        Path = "$EdgeAIDir\microservices\audio-analyzer"
        MainFile = "main.py"
        HealthUrl = "http://127.0.0.1:8010/health"
        Description = "Audio Analysis & Transcription"
    },
    @{
        Name = "rag-service"
        Port = 8020
        Path = "$KioskDir\rag-service"
        MainFile = "main.py"
        HealthUrl = "http://127.0.0.1:8020/health"
        Description = "RAG Service"
    },
    @{
        Name = "kiosk-core"
        Port = 8012
        Path = "$KioskDir"
        MainFile = "main.py"
        HealthUrl = "http://127.0.0.1:8012/health"
        Description = "Kiosk Core API"
    },
    @{
        Name = "kiosk-ui"
        Port = 7860
        Path = "$KioskDir"
        MainFile = "gradio_app.py"
        HealthUrl = $null  # Gradio doesn't have /health
        Description = "Gradio Web UI"
    }
)

# Check if a service is healthy
function Test-ServiceHealth {
    param([string]$HealthUrl)
    
    if (-not $HealthUrl) {
        return $true  # No health check available
    }
    
    try {
        $Response = Invoke-WebRequest -UseBasicParsing -Uri $HealthUrl -TimeoutSec 2 -ErrorAction SilentlyContinue
        return $Response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Get-ListeningPid {
    param([int]$Port)

    try {
        $Conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($Conn -and $Conn.OwningProcess) {
            return [int]$Conn.OwningProcess
        }
    }
    catch {}

    try {
        $Line = netstat -ano | Select-String ":$Port " | Select-String "LISTENING" | Select-Object -First 1
        if ($Line) {
            $Pid = ($Line.ToString().Trim() -split '\s+')[-1]
            if ($Pid -match '^\d+$') {
                return [int]$Pid
            }
        }
    }
    catch {}

    return $null
}

# Start a single service
function Start-Service {
    param($Service)

    if ($Service.Port) {
        $ExistingPid = Get-ListeningPid -Port $Service.Port
        if ($ExistingPid) {
            $IsHealthyExisting = Test-ServiceHealth -HealthUrl $Service.HealthUrl
            if ($IsHealthyExisting) {
                $Global:ServiceHealth[$Service.Name] = $true
                Write-Log "[READY] Reusing existing healthy process on port $($Service.Port) (PID $ExistingPid)" $Service.Name
                return $true
            }

            if ($Service.Name -eq "metrics-collector") {
                $Global:ServiceHealth[$Service.Name] = $true
                Write-Info "metrics-collector port $($Service.Port) is owned by PID $ExistingPid and not healthy; continuing without metrics collection"
                return $true
            }

            Write-Error-Custom "Port $($Service.Port) already in use for $($Service.Name) (PID $ExistingPid), but health check is failing"
            Write-Error-Custom "  Stop the existing process or run stop_kiosk.ps1 -Force, then retry"
            return $false
        }
    }

    if ($Service.Runtime -eq "powershell") {
        $MainFile = Join-Path $Service.Path $Service.MainFile

        if (-not (Test-Path $MainFile)) {
            Write-Error-Custom "Main file not found for $($Service.Name)"
            Write-Error-Custom "  Expected: $MainFile"
            return $false
        }

        try {
            $Job = Start-Job -ScriptBlock {
                param($MainFile, $ServicePath)
                Set-Location $ServicePath
                powershell -ExecutionPolicy Bypass -File $MainFile
            } -ArgumentList $MainFile, $Service.Path

            $Global:ProcessJobs[$Service.Name] = $Job
            $Global:ServiceHealth[$Service.Name] = $false

            Write-Log "Starting ($($Service.Description))..." $Service.Name
            return $true
        }
        catch {
            Write-Error-Custom "Failed to start $($Service.Name): $_"
            return $false
        }
    }
    
    $VenvPath = Join-Path $Service.Path "venv"
    $PythonExe = Join-Path $VenvPath "Scripts\python.exe"
    $MainFile = Join-Path $Service.Path $Service.MainFile
    
    if (-not (Test-Path $PythonExe)) {
        Write-Error-Custom "Python executable not found for $($Service.Name)"
        Write-Error-Custom "  Expected: $PythonExe"
        Write-Error-Custom "  Did you run setup_windows.ps1?"
        return $false
    }
    
    if (-not (Test-Path $MainFile)) {
        Write-Error-Custom "Main file not found for $($Service.Name)"
        Write-Error-Custom "  Expected: $MainFile"
        return $false
    }
    
    try {
        $Job = Start-Job -ScriptBlock {
            param($Python, $MainFile, $ServicePath, $ServiceName)
            Set-Location $ServicePath
            & $Python $MainFile
        } -ArgumentList $PythonExe, $MainFile, $Service.Path, $Service.Name
        
        $Global:ProcessJobs[$Service.Name] = $Job
        $Global:ServiceHealth[$Service.Name] = $false
        
        Write-Log "Starting ($($Service.Description))..." $Service.Name
        return $true
    }
    catch {
        Write-Error-Custom "Failed to start $($Service.Name): $_"
        return $false
    }
}

# Monitor services
function Monitor-Services {
    param([int]$TimeoutSeconds = 60)
    
    $StartTime = Get-Date
    $AllHealthy = $false
    
    while ((Get-Date) - $StartTime -lt (New-TimeSpan -Seconds $TimeoutSeconds)) {
        $HealthyCount = 0
        
        foreach ($Service in $Services) {
            $Job = $Global:ProcessJobs[$Service.Name]

            if (-not $Job) {
                $IsHealthy = Test-ServiceHealth -HealthUrl $Service.HealthUrl
                $Global:ServiceHealth[$Service.Name] = $IsHealthy
                if ($IsHealthy) {
                    $HealthyCount++
                }
                continue
            }

            # Prefer health over job state. Some servers (notably Gradio under
            # background jobs) can detach and leave the parent job Completed
            # while the service continues serving on its port.
            $IsHealthy = Test-ServiceHealth -HealthUrl $Service.HealthUrl
            $Global:ServiceHealth[$Service.Name] = $IsHealthy
            if ($IsHealthy) {
                $HealthyCount++
                if (-not $Silent) {
                    Write-Log "[READY] Ready on port $($Service.Port)" $Service.Name
                }
                continue
            }
            
            # Check if job exited before becoming healthy
            if ($Job.State -eq "Failed" -or $Job.State -eq "Completed" -or $Job.State -eq "Stopped") {
                if ($Service.Name -eq "metrics-collector") {
                    $Global:ServiceHealth[$Service.Name] = $true
                    Write-Info "metrics-collector exited during startup; continuing without metrics collection"
                    continue
                }

                Write-Error-Custom "Service $($Service.Name) exited before becoming healthy (state: $($Job.State))"

                $Output = Receive-Job -Job $Job -Keep -ErrorAction SilentlyContinue
                if ($Output) {
                    $Tail = @($Output | Select-Object -Last 8)
                    foreach ($Line in $Tail) {
                        if ($Line) {
                            Write-Log "[EXIT] $Line" $Service.Name
                        }
                    }
                }
                continue
            }

            Write-Log "[WAIT] Starting..." $Service.Name
        }
        
        # All services healthy?
        if ($HealthyCount -eq $Services.Count) {
            $AllHealthy = $true
            break
        }
        
        Start-Sleep -Milliseconds 500
    }
    
    if (-not $AllHealthy) {
        $Pending = @($Services | Where-Object { -not $Global:ServiceHealth[$_.Name] } | ForEach-Object { $_.Name })
        if ($Pending.Count -gt 0) {
            Write-Info "Startup timed out after $TimeoutSeconds seconds"
            Write-Info "Still not healthy: $($Pending -join ', ')"
        }
        Write-Info "Note: Some services may still be initializing (first run can take longer)"
    }
    
    return $AllHealthy
}

# Open browser
function Open-Browser {
    try {
        $Url = "http://127.0.0.1:7860"
        Write-Log "Opening browser..." launcher
        Start-Process $Url
        Write-Success "Browser opened to $Url"
    }
    catch {
        Write-Info "Could not auto-open browser. Visit: http://127.0.0.1:7860"
    }
}

# Display unified logs
function Show-Unified-Logs {
    Write-Header "UNIFIED SERVICE LOGS (Ctrl+C to stop)"
    
    while (-not $Global:ShutdownInProgress) {
        foreach ($ServiceName in $Global:ProcessJobs.Keys) {
            $Job = $Global:ProcessJobs[$ServiceName]
            
            if ($Job.State -ne "Running") {
                continue
            }
            
            $Output = Receive-Job -Job $Job -ErrorAction SilentlyContinue
            
            if ($Output) {
                foreach ($Line in $Output) {
                    if ($Line) {
                        Write-Log $Line $ServiceName
                    }
                }
            }
        }
        
        Start-Sleep -Milliseconds 200
    }
}

# Graceful shutdown
function Stop-AllServices {
    Write-Header "SHUTTING DOWN SERVICES"
    $Global:ShutdownInProgress = $true
    
    foreach ($ServiceName in $Global:ProcessJobs.Keys) {
        $Job = $Global:ProcessJobs[$ServiceName]
        
        if ($Job -and $Job.State -eq "Running") {
            Write-Log "Stopping..." $ServiceName
            Stop-Job -Job $Job -ErrorAction SilentlyContinue
            Remove-Job -Job $Job -ErrorAction SilentlyContinue
            Write-Success "$ServiceName stopped"
        }
    }
    
    Write-Success "All services stopped"
}

# Ctrl+C handler
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    Stop-AllServices
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

Write-Header "SMART KIOSK ASSISTANT - WINDOWS 11 LAUNCHER"

# Load environment
Load-Env

# Validate services exist
Write-Step "Validating service files..."
$AllValid = $true
foreach ($Service in $Services) {
    $MainFile = Join-Path $Service.Path $Service.MainFile
    if (-not (Test-Path $MainFile)) {
        Write-Error-Custom "Service file not found: $MainFile"
        $AllValid = $false
    }
}

if (-not $AllValid) {
    Write-Error-Custom "Some services are missing. Did you clone the repository correctly?"
    exit 1
}

Write-Success "All service files found"

# Start all services
Write-Step "Starting all services..."
$StartedCount = 0
foreach ($Service in $Services) {
    if (Start-Service -Service $Service) {
        $StartedCount++
        Start-Sleep -Milliseconds 500  # Stagger startup
    }
}

Write-Info "Started $StartedCount/$($Services.Count) services"

# Monitor health
Write-Step "Waiting for services to be ready..."
$AllHealthy = Monitor-Services -TimeoutSeconds $StartupTimeoutSeconds

if ($AllHealthy) {
    Write-Header "ALL SERVICES RUNNING"
    Write-Success "Smart Kiosk Assistant is ready!"
    
    Write-Host "`nAccess the application at:`n" -ForegroundColor Green
    Write-Host "  Browser UI:  http://127.0.0.1:7860" -ForegroundColor Cyan
    Write-Host "  Kiosk Core:  http://127.0.0.1:8012" -ForegroundColor Cyan
    Write-Host "  Audio:       http://127.0.0.1:8010" -ForegroundColor Cyan
    Write-Host "  TTS:         http://127.0.0.1:8011" -ForegroundColor Cyan
    Write-Host "  RAG:         http://127.0.0.1:8020" -ForegroundColor Cyan
    Write-Host "`nPress Ctrl+C to stop all services`n" -ForegroundColor Green
    
    # Open browser
    if (-not $NoBrowser) {
        Start-Sleep -Seconds 2
        Open-Browser
    }
}
else {
    $RunningUnhealthy = @($Services | Where-Object {
        $job = $Global:ProcessJobs[$_.Name]
        $job -and $job.State -eq "Running" -and -not $Global:ServiceHealth[$_.Name]
    } | ForEach-Object { $_.Name })

    if ($RunningUnhealthy.Count -gt 0) {
        Write-Info "Some services are still initializing: $($RunningUnhealthy -join ', ')"
        Write-Info "If this is first run, keep this window open and wait for model warmup/download to complete"
    }
    else {
        Write-Error-Custom "Some services failed to start"
        Write-Info "Check the logs above for details"
    }
}

# Show unified logs
Show-Unified-Logs

# Shutdown
Stop-AllServices
