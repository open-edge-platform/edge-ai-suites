#!/usr/bin/env pwsh
param(
    [switch]$SkipProxy,
    [switch]$Restart,
    [switch]$Help,
    [switch]$NoElevate,
    [switch]$Silent,
    [switch]$NoWindowsTerminal,
    [switch]$Electron
)

# ============================================================================
# WINDOWS-ONLY CHECK
# ============================================================================
$IsWindowsOS = $IsWindows -or ($PSVersionTable.PSVersion.Major -lt 6) -or ($env:OS -eq "Windows_NT")

if (-not $IsWindowsOS) {
    Write-Host "ERROR: This script is designed for Windows only." -ForegroundColor Red
    exit 1
}

# ============================================================================
# AUTO-ELEVATE TO ADMINISTRATOR
# ============================================================================
if (-not $NoElevate) {
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    
    if (-not $isAdmin) {
        Write-Host "Requesting Administrator privileges..." -ForegroundColor Yellow
        
        $argList = "-NoExit -ExecutionPolicy Bypass -File `"$PSCommandPath`""
        if ($SkipProxy) { $argList += " -SkipProxy" }
        if ($Restart) { $argList += " -Restart" }
        if ($Help) { $argList += " -Help" }
        if ($Silent) { $argList += " -Silent" }
        if ($NoWindowsTerminal) { $argList += " -NoWindowsTerminal" }
        if ($Electron) { $argList += " -Electron" }
        $argList += " -NoElevate"  # Prevent infinite elevation loop
        
        try {
            Start-Process powershell -Verb RunAs -ArgumentList $argList
            Write-Host "Elevated window launched. You can close this window." -ForegroundColor Green
            exit 0
        } catch {
            Write-Host "Failed to elevate. Please run as Administrator manually." -ForegroundColor Red
            Write-Host "Right-click PowerShell -> Run as Administrator" -ForegroundColor Yellow
            exit 1
        }
    }
}

if ($Help) {
    Write-Host @"
Smart Classroom Startup Script

Usage: ./start-smart-classroom.ps1 [-SkipProxy] [-Restart] [-Silent] [-NoElevate] [-NoWindowsTerminal] [-Electron] [-Help]

Options:
    -SkipProxy           Skip proxy configuration prompts
    -Restart             Kill existing services and restart (no prompt)
    -Silent              Unattended mode - auto-restart, skip all prompts
    -NoElevate           Skip auto-elevation to Administrator (Windows)
    -NoWindowsTerminal   Use Invoke-WmiMethod instead of Windows Terminal (for remote sessions)
    -Electron            Launch the UI as an Electron desktop app instead of a browser tab
    -Help                Show this help message

Note: On Windows, the script automatically requests Administrator privileges.

Services Launched (in order):
    1. Backend (port 8000)     - Main Python pipeline service (with paddleocr if OCR enabled)
    2. Content Search (9011)   - RAG, video summarization, semantic search
    3. Frontend (port 5173)    - React UI (opens as an Electron desktop window when -Electron is set;
                                 the dev server still runs on port 5173)

"@ -ForegroundColor Cyan
    exit 0
}

# ============================================================================
# CTRL+C HANDLER - Stop services on script exit
# ============================================================================
$script:servicesStarted = $false

function Stop-AllServices {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "   STOPPING ALL SERVICES..." -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host ""
    
    $ports = @(8000, 9011, 5173)
    $portNames = @{ 8000 = "Backend"; 9011 = "Content Search"; 5173 = "Frontend" }
    
    foreach ($port in $ports) {
        Write-Host "  Stopping $($portNames[$port]) (port $port)..." -ForegroundColor Yellow
        
        # Retry killing processes on this port up to 3 times
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
                if ($connections) {
                    $procIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
                    foreach ($procId in $procIds) {
                        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                    }
                }
            } catch {
                # Continue to next method
            }
            
            Start-Sleep -Milliseconds 300
        }
        
        # Use taskkill as additional method
        try {
            taskkill /F /FI "LocalPort eq $port" 2>$null
        } catch {}
        
        Start-Sleep -Seconds 1
    }

    $connections = Get-NetTCPConnection -LocalPort 9090 -ErrorAction SilentlyContinue
    if ($connections) {
        Write-Host "  Stopping ChromaDB (port 9090)..." -ForegroundColor Yellow
        $procIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($procId in $procIds) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }

    $connections = Get-NetTCPConnection -LocalPort 9900 -ErrorAction SilentlyContinue
    if ($connections) {
        Write-Host "  Stopping VLM (port 9900)..." -ForegroundColor Yellow
        $procIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($procId in $procIds) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }

    $connections = Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue
    if ($connections) {
        Write-Host "  Stopping Preprocess (port 8001)..." -ForegroundColor Yellow
        $procIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($procId in $procIds) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }

    $connections = Get-NetTCPConnection -LocalPort 9990 -ErrorAction SilentlyContinue
    if ($connections) {
        Write-Host "  Stopping Ingest (port 9990)..." -ForegroundColor Yellow
        $procIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($procId in $procIds) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
    
    # Comprehensive process cleanup (silent)
    
    # Kill all Python processes (multiple attempts)
    try {
        Get-Process python, python.exe -ErrorAction SilentlyContinue | ForEach-Object {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    } catch {}
    
    # Kill all npm/node processes
    try {
        Get-Process node, npm -ErrorAction SilentlyContinue | ForEach-Object {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    } catch {}
    
    # Kill uvicorn processes specifically
    try {
        Get-Process uvicorn -ErrorAction SilentlyContinue | ForEach-Object {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    } catch {}
    
    # Final wait for ports to be freed
    Start-Sleep -Seconds 3
    
    # Verify ports are free
    $portsToVerify = @(8000, 9011, 9090, 9900, 8001, 9990, 5173)
    foreach ($port in $portsToVerify) {
        try {
            $connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
            if ($connection) {
                taskkill /F /PID $connection.OwningProcess 2>$null
                Start-Sleep -Seconds 1
            }
        } catch {}
    }
    
    Write-Host ""
    Write-Host "Services stopped.. Wait for the processes to get terminated...before start again..." -ForegroundColor Green
}

# Register Ctrl+C handler
if (-not $Silent) {
    [Console]::TreatControlCAsInput = $false
}
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    if ($script:servicesStarted) {
        Stop-AllServices
    }
}

trap {
    Write-Host ""
    Write-Host "  Script interrupted at line $($_.InvocationInfo.ScriptLineNumber) with $($_.Exception.Message)" -ForegroundColor Red
    if ($script:servicesStarted) {
        Stop-AllServices
    }
    for ($i = 30; $i -gt 0; $i--) {
        Start-Sleep -Seconds 1
    }
    exit 1
}

# ============================================================================
# PLATFORM DETECTION
# ============================================================================
$IsLinuxOS = $IsLinux -or ($PSVersionTable.Platform -eq "Unix")

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   SMART CLASSROOM STARTUP SCRIPT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Platform: $(if ($IsWindowsOS) { 'Windows' } else { 'Linux' })" -ForegroundColor Yellow
Write-Host "PowerShell: $($PSVersionTable.PSVersion)" -ForegroundColor Yellow
if ($IsWindowsOS) {
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    Write-Host "Admin: $(if ($isAdmin) { 'Yes' } else { 'No' })" -ForegroundColor $(if ($isAdmin) { 'Green' } else { 'Yellow' })
}
Write-Host ""

# ============================================================================
# SCRIPT DIRECTORY DETECTION
# ============================================================================
$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
}
if (-not $ScriptDir) {
    $ScriptDir = Get-Location
}

Write-Host "Working Directory: $ScriptDir" -ForegroundColor Gray
Set-Location $ScriptDir

# ============================================================================
# CHECK FOR RUNNING SERVICES
# ============================================================================
function Test-PortInUse {
    param([int]$Port)
    
    if ($IsWindowsOS) {
        $connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        return $null -ne $connection
    } else {
        $result = bash -c "ss -tuln | grep -q ':$Port '" 2>$null
        return $LASTEXITCODE -eq 0
    }
}

function Stop-ServiceOnPort {
    param([int]$Port, [string]$ServiceName)
    
    if ($IsWindowsOS) {
        $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        if ($connections) {
            Write-Host "  Stopping $ServiceName on port $Port..." -ForegroundColor Yellow
            $procIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
            foreach ($procId in $procIds) {
                try {
                    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                    Write-Host "    Killed process $procId" -ForegroundColor Gray
                } catch {
                    Write-Host "    Could not kill process $procId" -ForegroundColor Yellow
                }
            }
            Start-Sleep -Seconds 2
        }
    } else {
        $result = bash -c "ss -tuln | grep -q ':$Port '" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  Stopping $ServiceName on port $Port..." -ForegroundColor Yellow
            bash -c "fuser -k $Port/tcp" 2>$null
            Start-Sleep -Seconds 2
        }
    }
}

# Function to clean up virtual environments for fresh restart
function Remove-VirtualEnvironments {
    Write-Host "  Cleaning up virtual environments..." -ForegroundColor Yellow
    
    $parentDir = Split-Path $ScriptDir -Parent
    $backendVenv = Join-Path $parentDir "smartclassroom"
    $contentSearchVenv = Join-Path $ScriptDir "content_search\venv_content_search"
    
    Write-Host "    Terminating Python processes that may be using venvs..." -ForegroundColor Gray
    Get-Process -Name "python" -ErrorAction SilentlyContinue | ForEach-Object {
        $procPath = $_.Path
        if ($procPath -and ($procPath -like "*smartclassroom*" -or $procPath -like "*venv_content_search*")) {
            Write-Host "      Killing Python process $($_.Id): $procPath" -ForegroundColor Gray
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Seconds 2
    
    if (Test-Path $backendVenv) {
        Write-Host "    Removing Backend venv: $backendVenv" -ForegroundColor Gray
        for ($i = 1; $i -le 3; $i++) {
            Remove-Item -Path $backendVenv -Recurse -Force -ErrorAction SilentlyContinue
            if (-not (Test-Path $backendVenv)) { break }
            Write-Host "      Retry $i - waiting for file handles to release..." -ForegroundColor DarkYellow
            Start-Sleep -Seconds 2
        }
        if (Test-Path $backendVenv) {
            Write-Host "    WARNING: Could not fully remove Backend venv. Some files may be locked." -ForegroundColor Yellow
        } else {
            Write-Host "    Backend venv removed." -ForegroundColor Gray
        }
    } else {
        Write-Host "    Backend venv not found (will be created fresh)" -ForegroundColor Gray
    }
    
    if (Test-Path $contentSearchVenv) {
        Write-Host "    Removing Content Search venv: $contentSearchVenv" -ForegroundColor Gray
        for ($i = 1; $i -le 3; $i++) {
            Remove-Item -Path $contentSearchVenv -Recurse -Force -ErrorAction SilentlyContinue
            if (-not (Test-Path $contentSearchVenv)) { break }
            Write-Host "      Retry $i - waiting for file handles to release..." -ForegroundColor DarkYellow
            Start-Sleep -Seconds 2
        }
        if (Test-Path $contentSearchVenv) {
            Write-Host "    WARNING: Could not fully remove Content Search venv. Some files may be locked." -ForegroundColor Yellow
        } else {
            Write-Host "    Content Search venv removed." -ForegroundColor Gray
        }
    } else {
        Write-Host "    Content Search venv not found (will be created fresh)" -ForegroundColor Gray
    }
    
    Write-Host "  Virtual environments cleaned." -ForegroundColor Green
}

Write-Host ""
Write-Host "[PRE-CHECK] DETECTING RUNNING SERVICES" -ForegroundColor Cyan
Write-Host "--------------------------------------" -ForegroundColor Cyan

# Wait a moment for ports to be fully released from previous session
Write-Host "  Checking port status..." -ForegroundColor Gray
Start-Sleep -Seconds 2

# Enhanced port checking that verifies services are actually listening (not just in TIME_WAIT)
function Test-ServiceListening {
    param([int]$Port)
    
    try {
        $connection = Get-NetTCPConnection -LocalPort $Port -State "Listen" -ErrorAction SilentlyContinue
        return $null -ne $connection
    } catch {
        return $false
    }
}

$backendRunning = Test-ServiceListening -Port 8000
$contentSearchRunning = Test-ServiceListening -Port 9011
$frontendRunning = Test-ServiceListening -Port 5173

$anyRunning = $backendRunning -or $contentSearchRunning -or $frontendRunning

# Initialize skip flags based on running state
$script:skipBackend = $backendRunning
$script:skipContentSearch = $contentSearchRunning
$script:skipFrontend = $frontendRunning

Write-Host ""
Write-Host "  Service Status:" -ForegroundColor Yellow
if ($backendRunning) { 
    Write-Host "    [RUNNING] Backend (port 8000)" -ForegroundColor Green 
} else { 
    Write-Host "    [STOPPED] Backend (port 8000)" -ForegroundColor Red 
}
if ($contentSearchRunning) { 
    Write-Host "    [RUNNING] Content Search (port 9011)" -ForegroundColor Green 
} else { 
    Write-Host "    [STOPPED] Content Search (port 9011)" -ForegroundColor Red 
}
if ($frontendRunning) { 
    Write-Host "    [RUNNING] Frontend (port 5173)" -ForegroundColor Green 
} else { 
    Write-Host "    [STOPPED] Frontend (port 5173)" -ForegroundColor Red 
}
Write-Host ""

if ($Restart) {
    # -Restart flag: stop all running services and start fresh
    Write-Host "  -Restart flag specified. Stopping all running services..." -ForegroundColor Yellow
    if ($backendRunning) { Stop-ServiceOnPort -Port 8000 -ServiceName "Backend" }
    if ($contentSearchRunning) {
        Stop-ServiceOnPort -Port 9011 -ServiceName "Content Search"
    }
    Stop-ServiceOnPort -Port 9090 -ServiceName "ChromaDB"
    Stop-ServiceOnPort -Port 9900 -ServiceName "VLM"
    Stop-ServiceOnPort -Port 8001 -ServiceName "Preprocess"
    Stop-ServiceOnPort -Port 9990 -ServiceName "Ingest"
    if ($frontendRunning) { Stop-ServiceOnPort -Port 5173 -ServiceName "Frontend" }

    if ($Silent) {
        Write-Host "  Silent mode: keeping existing virtual environments" -ForegroundColor Gray
        $deleteVenvs = "N"
    } else {
        $deleteVenvs = Read-Host "  Delete virtual environments and create new? (Y/N)"
    }

    if ($deleteVenvs.ToUpper() -eq "Y") {
        Remove-VirtualEnvironments
        Write-Host "  All services will be restarted with new environments." -ForegroundColor Green
    } else {
        Write-Host "  Keeping existing virtual environments. Restarting services." -ForegroundColor Green
    }
    
    $script:skipBackend = $false
    $script:skipContentSearch = $false
    $script:skipFrontend = $false
} elseif ($anyRunning) {
    if ($Silent) {
        Write-Host "  Silent mode: auto-restarting all running services..." -ForegroundColor Yellow
        $choice = "R"
    } else {
        Write-Host "  What would you like to do?" -ForegroundColor Yellow
        Write-Host "    [R] Restart - Kill services and restart" -ForegroundColor White
        Write-Host "    [S] Skip    - Use existing services (only start missing ones)" -ForegroundColor White
        Write-Host "    [A] Abort   - Stop all services and exit" -ForegroundColor White
        Write-Host "    [E] Exit    - Exit script without changes" -ForegroundColor White
        Write-Host ""

        $choice = Read-Host "  Enter choice (R/S/A/E)"
    }
    
    switch ($choice.ToUpper()) {
        "R" {
            Write-Host ""
            Write-Host "  Restarting all services..." -ForegroundColor Yellow
            if ($backendRunning) { Stop-ServiceOnPort -Port 8000 -ServiceName "Backend" }
            if ($contentSearchRunning) {
                Stop-ServiceOnPort -Port 9011 -ServiceName "Content Search"
            }
            Stop-ServiceOnPort -Port 9090 -ServiceName "ChromaDB"
            Stop-ServiceOnPort -Port 9900 -ServiceName "VLM"
            Stop-ServiceOnPort -Port 8001 -ServiceName "Preprocess"
            Stop-ServiceOnPort -Port 9990 -ServiceName "Ingest"
            if ($frontendRunning) { Stop-ServiceOnPort -Port 5173 -ServiceName "Frontend" }

            if ($Silent) {
                Write-Host "  Silent mode: keeping existing virtual environments" -ForegroundColor Gray
                $deleteVenvs = "N"
            } else {
                $deleteVenvs = Read-Host "  Delete virtual environments and create new? (Y/N)"
            }

            if ($deleteVenvs.ToUpper() -eq "Y") {
                Remove-VirtualEnvironments
            } else {
                Write-Host "  Keeping existing virtual environments." -ForegroundColor Gray
            }
            
            $script:skipBackend = $false
            $script:skipContentSearch = $false
            $script:skipFrontend = $false
            Write-Host "  Existing services stopped." -ForegroundColor Green
        }
        "S" {
            Write-Host ""
            Write-Host "  Smart Start: Keeping running services, starting stopped ones." -ForegroundColor Yellow
            $script:skipBackend = $backendRunning
            $script:skipContentSearch = $contentSearchRunning
            $script:skipFrontend = $frontendRunning
        }
        "A" {
            Write-Host ""
            Write-Host "  Stopping all services..." -ForegroundColor Yellow
            if ($backendRunning) { Stop-ServiceOnPort -Port 8000 -ServiceName "Backend" }
            if ($contentSearchRunning) { 
                Stop-ServiceOnPort -Port 9011 -ServiceName "Content Search"
            }
            Stop-ServiceOnPort -Port 9090 -ServiceName "ChromaDB"
            Stop-ServiceOnPort -Port 9900 -ServiceName "VLM"
            Stop-ServiceOnPort -Port 8001 -ServiceName "Preprocess"
            Stop-ServiceOnPort -Port 9990 -ServiceName "Ingest"
            if ($frontendRunning) { Stop-ServiceOnPort -Port 5173 -ServiceName "Frontend" }
            Write-Host "  All services stopped. Waiting for processes to terminate...Before starting new services..." -ForegroundColor Green
            exit 0
        }
        "E" {
            Write-Host ""
            Write-Host "  Exiting without changes. Services still running." -ForegroundColor Yellow
            exit 0
        }
        default {
            Write-Host ""
            Write-Host "  Invalid choice. Aborting." -ForegroundColor Red
            exit 1
        }
    }
} else {
    Write-Host "  No main services detected." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Stopping any orphaned processes (ChromaDB, VLM, Preprocess, Ingest, Python)..." -ForegroundColor Yellow
    
    Stop-ServiceOnPort -Port 9090 -ServiceName "ChromaDB"
    Stop-ServiceOnPort -Port 9900 -ServiceName "VLM"
    Stop-ServiceOnPort -Port 8001 -ServiceName "Preprocess"
    Stop-ServiceOnPort -Port 9990 -ServiceName "Ingest"
    
    Get-Process -Name "python" -ErrorAction SilentlyContinue | ForEach-Object {
        $procPath = $_.Path
        if ($procPath -and ($procPath -like "*smartclassroom*" -or $procPath -like "*venv_content_search*")) {
            Write-Host "    Killing orphaned Python: $($_.Id)" -ForegroundColor Gray
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    }
    
    Write-Host ""
    Write-Host "  Starting all services..." -ForegroundColor Green
}

# Summary
Write-Host ""
Write-Host "  Action Summary:" -ForegroundColor Cyan
if ($script:skipBackend) { Write-Host "    Backend:        SKIP (already running)" -ForegroundColor Gray }
else { Write-Host "    Backend:        START" -ForegroundColor Green }
if ($script:skipContentSearch) { Write-Host "    Content Search: SKIP (already running)" -ForegroundColor Gray }
else { Write-Host "    Content Search: START" -ForegroundColor Green }
if ($script:skipFrontend) { Write-Host "    Frontend:       SKIP (already running)" -ForegroundColor Gray }
else { Write-Host "    Frontend:       START" -ForegroundColor Green }

# ============================================================================
# STEP 1: PROXY CONFIGURATION (Persistent)
# ============================================================================
Write-Host ""
Write-Host "[1/4] PROXY CONFIGURATION" -ForegroundColor Green
Write-Host "-------------------------" -ForegroundColor Green

$httpProxy = ""
$httpsProxy = ""
$noProxy = ""
$proxyConfigFile = Join-Path $ScriptDir ".proxy-config"

if (-not $SkipProxy -and -not $Silent) {
    if (Test-Path $proxyConfigFile) {
        $proxyConfig = Get-Content $proxyConfigFile | ConvertFrom-Json
        $httpProxy = $proxyConfig.httpProxy
        $httpsProxy = $proxyConfig.httpsProxy
        $noProxy = $proxyConfig.noProxy

        Write-Host ""
        Write-Host "  Saved proxy settings found:" -ForegroundColor Cyan
        if ($httpProxy) { Write-Host "    HTTP_PROXY:  $httpProxy" -ForegroundColor Gray }
        if ($httpsProxy) { Write-Host "    HTTPS_PROXY: $httpsProxy" -ForegroundColor Gray }
        if ($noProxy) { Write-Host "    NO_PROXY:    $noProxy" -ForegroundColor Gray }
        if (-not $httpProxy -and -not $httpsProxy) { 
            Write-Host "    (No proxy configured in .proxy-config)" -ForegroundColor Gray 
            
            # Check environment for proxy settings
            Write-Host ""
            Write-Host "  Checking environment for existing proxy settings..." -ForegroundColor Gray
            $envHttpProxy = if ($env:HTTP_PROXY) { $env:HTTP_PROXY } elseif ($env:http_proxy) { $env:http_proxy } else { "" }
            $envHttpsProxy = if ($env:HTTPS_PROXY) { $env:HTTPS_PROXY } elseif ($env:https_proxy) { $env:https_proxy } else { "" }
            $envNoProxy = if ($env:NO_PROXY) { $env:NO_PROXY } elseif ($env:no_proxy) { $env:no_proxy } else { "" }
            
            $envProxies = Get-ChildItem Env:\*proxy* -ErrorAction SilentlyContinue
            if ($envProxies) {
                $envProxies | ForEach-Object {
                    Write-Host "    Found: $($_.Name) = $($_.Value)" -ForegroundColor Cyan
                }
                Write-Host ""
                Write-Host "  Environment variables detected. You can save these to .proxy-config." -ForegroundColor Yellow
            } else {
                Write-Host "    (No proxy environment variables found)" -ForegroundColor Gray
            }
        }
        Write-Host ""

        if (-not $httpProxy -and -not $httpsProxy -and ($envHttpProxy -or $envHttpsProxy)) {
            Write-Host "  [Y] Yes - Configure different proxy settings" -ForegroundColor White
            Write-Host "  [N] No  - Save environment proxy settings to .proxy-config" -ForegroundColor White
            Write-Host "  [S] Skip - No proxy (direct connection)" -ForegroundColor White
        } else {
            Write-Host "  [Y] Yes - Change proxy settings" -ForegroundColor White
            Write-Host "  [N] No  - Use saved proxy settings" -ForegroundColor White
            Write-Host "  [S] Skip - No proxy (direct connection)" -ForegroundColor White
        }
        Write-Host ""
        $changeProxy = Read-Host "Do you want to change proxy settings? (Y/N/S)"
        
        if ($changeProxy -match "^[Yy]") {
            Write-Host ""
            Write-Host "Enter new proxy settings (press Enter to keep current value):" -ForegroundColor Yellow
            Write-Host ""
            
            $newHttpProxy = Read-Host "HTTP_PROXY  [$httpProxy]"
            $newHttpsProxy = Read-Host "HTTPS_PROXY [$httpsProxy]"
            $newNoProxy = Read-Host "NO_PROXY    [$noProxy]"
            
            if ($newHttpProxy) { $httpProxy = $newHttpProxy }
            if ($newHttpsProxy) { $httpsProxy = $newHttpsProxy }
            if ($newNoProxy) { $noProxy = $newNoProxy }
            
            $proxyConfig = @{
                httpProxy = $httpProxy
                httpsProxy = $httpsProxy
                noProxy = $noProxy
            }
            $proxyConfig | ConvertTo-Json | Set-Content $proxyConfigFile
            Write-Host "  Proxy settings updated and saved." -ForegroundColor Green
        } elseif ($changeProxy -match "^[Ss]") {
            $httpProxy = ""
            $httpsProxy = ""
            $noProxy = ""
            Write-Host "  No proxy - using direct connection." -ForegroundColor Yellow
        } else {
            # If .proxy-config is empty but environment has proxy, save environment values
            if (-not $httpProxy -and -not $httpsProxy -and ($envHttpProxy -or $envHttpsProxy)) {
                $httpProxy = $envHttpProxy
                $httpsProxy = $envHttpsProxy
                $noProxy = $envNoProxy
                
                $proxyConfig = @{
                    httpProxy = $httpProxy
                    httpsProxy = $httpsProxy
                    noProxy = $noProxy
                }
                $proxyConfig | ConvertTo-Json | Set-Content $proxyConfigFile
                Write-Host "  Environment proxy settings saved to .proxy-config:" -ForegroundColor Green
                if ($httpProxy) { Write-Host "    HTTP_PROXY:  $httpProxy" -ForegroundColor Gray }
                if ($httpsProxy) { Write-Host "    HTTPS_PROXY: $httpsProxy" -ForegroundColor Gray }
                if ($noProxy) { Write-Host "    NO_PROXY:    $noProxy" -ForegroundColor Gray }
            } else {
                Write-Host "  Using saved proxy settings." -ForegroundColor Gray
            }
        }
    } else {
        Write-Host ""
        Write-Host "  No proxy configuration found in .proxy-config file." -ForegroundColor Gray
        Write-Host "  Checking environment for existing proxy settings..." -ForegroundColor Gray
        Write-Host ""
        
        # Check environment variables for proxy settings
        $envHttpProxy = if ($env:HTTP_PROXY) { $env:HTTP_PROXY } elseif ($env:http_proxy) { $env:http_proxy } else { "" }
        $envHttpsProxy = if ($env:HTTPS_PROXY) { $env:HTTPS_PROXY } elseif ($env:https_proxy) { $env:https_proxy } else { "" }
        $envNoProxy = if ($env:NO_PROXY) { $env:NO_PROXY } elseif ($env:no_proxy) { $env:no_proxy } else { "" }
        
        $envProxies = Get-ChildItem Env:\*proxy* -ErrorAction SilentlyContinue
        if ($envProxies) {
            $envProxies | ForEach-Object {
                Write-Host "    Found: $($_.Name) = $($_.Value)" -ForegroundColor Cyan
            }
            Write-Host ""
            Write-Host "  Environment variables detected. You can save these or configure different settings." -ForegroundColor Yellow
        } else {
            Write-Host "    (No proxy environment variables found)" -ForegroundColor Gray
        }
        Write-Host ""
        
        if ($envHttpProxy -or $envHttpsProxy) {
            Write-Host "  [Y] Yes - Configure different proxy settings" -ForegroundColor White
            Write-Host "  [N] No  - Save current environment proxy settings to .proxy-config" -ForegroundColor White
        } else {
            Write-Host "  [Y] Yes - Configure proxy" -ForegroundColor White
            Write-Host "  [N] No  - No proxy (direct connection)" -ForegroundColor White
        }
        Write-Host ""
        $configureProxy = Read-Host "Do you want to configure a proxy? (Y/N)"
        
        if ($configureProxy -match "^[Yy]") {
            Write-Host ""
            Write-Host "Enter proxy settings:" -ForegroundColor Yellow
            Write-Host "  (Common Intel proxy: http://proxy-iind.intel.com:912)" -ForegroundColor DarkGray
            Write-Host ""
            
            $httpProxy = Read-Host "HTTP_PROXY"
            $httpsProxy = Read-Host "HTTPS_PROXY (press Enter to use same as HTTP)"
            $noProxy = Read-Host "NO_PROXY"
            
            if (-not $httpsProxy -and $httpProxy) { $httpsProxy = $httpProxy }
            
            $proxyConfig = @{
                httpProxy = $httpProxy
                httpsProxy = $httpsProxy
                noProxy = $noProxy
            }
            $proxyConfig | ConvertTo-Json | Set-Content $proxyConfigFile
            Write-Host "  Proxy settings saved to .proxy-config" -ForegroundColor Green
        } else {
            # If environment variables exist, save them; otherwise save empty config
            if ($envHttpProxy -or $envHttpsProxy) {
                $httpProxy = $envHttpProxy
                $httpsProxy = $envHttpsProxy
                $noProxy = $envNoProxy
                
                $proxyConfig = @{
                    httpProxy = $httpProxy
                    httpsProxy = $httpsProxy
                    noProxy = $noProxy
                }
                $proxyConfig | ConvertTo-Json | Set-Content $proxyConfigFile
                Write-Host "  Environment proxy settings saved to .proxy-config:" -ForegroundColor Green
                if ($httpProxy) { Write-Host "    HTTP_PROXY:  $httpProxy" -ForegroundColor Gray }
                if ($httpsProxy) { Write-Host "    HTTPS_PROXY: $httpsProxy" -ForegroundColor Gray }
                if ($noProxy) { Write-Host "    NO_PROXY:    $noProxy" -ForegroundColor Gray }
            } else {
                $proxyConfig = @{
                    httpProxy = ""
                    httpsProxy = ""
                    noProxy = ""
                }
                $proxyConfig | ConvertTo-Json | Set-Content $proxyConfigFile
                Write-Host "  No proxy configured. Settings saved." -ForegroundColor Gray
            }
        }
    }
    
    if ($httpProxy) {
        $env:HTTP_PROXY = $httpProxy
        $env:http_proxy = $httpProxy
        Write-Host "  Applied HTTP_PROXY=$httpProxy" -ForegroundColor Gray
    }
    
    if ($httpsProxy) {
        $env:HTTPS_PROXY = $httpsProxy
        $env:https_proxy = $httpsProxy
        Write-Host "  Applied HTTPS_PROXY=$httpsProxy" -ForegroundColor Gray
    }
    
    if ($noProxy) {
        $env:NO_PROXY = $noProxy
        $env:no_proxy = $noProxy
        Write-Host "  Applied NO_PROXY=$noProxy" -ForegroundColor Gray
    }
} else {
    # -SkipProxy flag: load saved settings without prompting user
    Write-Host "  Loading proxy from .proxy-config (skipping prompts)..." -ForegroundColor Gray
    
    if (Test-Path $proxyConfigFile) {
        $proxyConfig = Get-Content $proxyConfigFile | ConvertFrom-Json
        $httpProxy = $proxyConfig.httpProxy
        $httpsProxy = $proxyConfig.httpsProxy
        $noProxy = $proxyConfig.noProxy
        
        if ($httpProxy) {
            $env:HTTP_PROXY = $httpProxy
            $env:http_proxy = $httpProxy
            Write-Host "  Applied HTTP_PROXY=$httpProxy" -ForegroundColor Gray
        }
        
        if ($httpsProxy) {
            $env:HTTPS_PROXY = $httpsProxy
            $env:https_proxy = $httpsProxy
            Write-Host "  Applied HTTPS_PROXY=$httpsProxy" -ForegroundColor Gray
        }
        
        if ($noProxy) {
            $env:NO_PROXY = $noProxy
            $env:no_proxy = $noProxy
            Write-Host "  Applied NO_PROXY=$noProxy" -ForegroundColor Gray
        }
        
        if (-not $httpProxy -and -not $httpsProxy) {
            Write-Host "  Checking environment for existing proxy settings..." -ForegroundColor Gray
            Get-ChildItem Env:\*proxy* -ErrorAction SilentlyContinue | ForEach-Object {
                Write-Host "    Found: $($_.Name) = $($_.Value)" -ForegroundColor DarkGray
            }
            Write-Host "  No proxy configured in .proxy-config" -ForegroundColor Gray
        }
    } else {
        Write-Host "  Checking environment for existing proxy settings..." -ForegroundColor Gray
        Get-ChildItem Env:\*proxy* -ErrorAction SilentlyContinue | ForEach-Object {
            Write-Host "    Found: $($_.Name) = $($_.Value)" -ForegroundColor DarkGray
        }
        Write-Host "  No .proxy-config file found" -ForegroundColor Gray
    }
}

# ============================================================================
# STEP 2: WINDOWS LONG PATHS & EXECUTION POLICY
# ============================================================================
Write-Host ""
Write-Host "[2/4] SYSTEM CONFIGURATION" -ForegroundColor Green
Write-Host "--------------------------" -ForegroundColor Green

if ($IsWindowsOS) {
    Write-Host "  Enabling Windows Long Paths..." -ForegroundColor Gray
    
    try {
        $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        
        if ($isAdmin) {
            $regPath = "HKLM:\System\CurrentControlSet\Control\FileSystem"
            $currentValue = Get-ItemProperty -Path $regPath -Name "LongPathsEnabled" -ErrorAction SilentlyContinue
            
            if ($currentValue.LongPathsEnabled -ne 1) {
                New-ItemProperty -Path $regPath -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force | Out-Null
                Write-Host "  Long paths enabled successfully" -ForegroundColor Green
            } else {
                Write-Host "  Long paths already enabled" -ForegroundColor Gray
            }
        } else {
            Write-Host "  Skipped long paths (requires Administrator)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  Warning: Could not modify registry - $($_.Exception.Message)" -ForegroundColor Yellow
    }
    
    Write-Host "  Setting execution policy to Bypass..." -ForegroundColor Gray
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction SilentlyContinue
    Write-Host "  Execution policy set" -ForegroundColor Gray
    
} else {
    Write-Host "  Linux detected - skipping Windows-specific configuration" -ForegroundColor Gray
}

# ============================================================================
# STEP 3: CHECK OCR CONFIG
# ============================================================================
Write-Host ""
Write-Host "[3/4] CHECKING CONFIGURATION" -ForegroundColor Green
Write-Host "----------------------------" -ForegroundColor Green

$configPath = Join-Path $ScriptDir "config.yaml"
if (Test-Path $configPath) {
    $configContent = Get-Content $configPath -Raw
    if ($configContent -match "ocr:\s*\n\s*enabled:\s*true") {
        Write-Host "  OCR: Enabled" -ForegroundColor Yellow
    } else {
        Write-Host "  OCR: Disabled" -ForegroundColor Gray
    }
} else {
    Write-Host "  config.yaml not found, assuming OCR disabled" -ForegroundColor Gray
}

# Check Node.js
$npmExists = Get-Command npm -ErrorAction SilentlyContinue
if ($npmExists) {
    Write-Host "  Node.js/npm: Found ($(npm --version))" -ForegroundColor Green
} else {
    Write-Host "  Node.js/npm: Not found - Frontend will fail!" -ForegroundColor Red
}

# ============================================================================
# STEP 4: LAUNCH SERVICES
# ============================================================================
Write-Host ""
Write-Host "[4/4] LAUNCHING SERVICES" -ForegroundColor Green
Write-Host "------------------------" -ForegroundColor Green
Write-Host ""
Write-Host "Terminals will launch sequentially with health checks:" -ForegroundColor Yellow
Write-Host "  1. Backend (port 8000) - wait until healthy" -ForegroundColor White
Write-Host "  2. Content Search (port 9011) - wait until healthy" -ForegroundColor White
Write-Host "  3. Frontend (port 5173)" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop all services and exit." -ForegroundColor DarkGray
Write-Host ""

# Mark that services are being started (for Ctrl+C handler)
$script:servicesStarted = $true

# Health check function (no timeout - relies on crash detection)
function Wait-ForService {
    param(
        [string]$ServiceName,
        [string]$Url,
        [int]$Port,
        [int[]]$DependentPorts = @(),
        [string]$CommandLinePattern = "",  # Pattern to match in process command line (e.g., "main.py", "start_services.py")
        [int]$IntervalSeconds = 5
    )
    
    $elapsed = 0
    $initialGracePeriod = 60  # 1 minute grace period before checking for crashes
    Write-Host "  Waiting for $ServiceName to be healthy..." -ForegroundColor Gray
    Write-Host "  Health check: $Url" -ForegroundColor DarkGray
    Write-Host "  (No timeout - will wait until service is ready or crashes)" -ForegroundColor DarkGray
    
    while ($true) {
        # After initial grace period, check if dependent services are still running
        if ($elapsed -ge $initialGracePeriod) {
            foreach ($depPort in $DependentPorts) {
                $depListening = Get-NetTCPConnection -LocalPort $depPort -State Listen -ErrorAction SilentlyContinue
                if (-not $depListening) {
                    Write-Host ""
                    Write-Host ""
                    Write-Host "========================================" -ForegroundColor Red
                    Write-Host "  ERROR: DEPENDENT SERVICE STOPPED" -ForegroundColor Red
                    Write-Host "========================================" -ForegroundColor Red
                    Write-Host ""
                    Write-Host "  Service on port $depPort is no longer running." -ForegroundColor Red
                    Write-Host "  Cannot continue starting $ServiceName." -ForegroundColor Yellow
                    Write-Host ""
                    Write-Host "  NOTE: $ServiceName might still be running in its terminal." -ForegroundColor DarkYellow
                    Write-Host "        Please check and close it manually if needed." -ForegroundColor DarkYellow
                    Write-Host ""
                    return $false
                }
            }
        }
        
        # After initial grace period, check if service crashed
        if ($elapsed -ge $initialGracePeriod -and $Port -gt 0) {
            $listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
            if (-not $listening) {
                # Port not listening - check if the service process is still running
                $serviceRunning = $false
                
                # Get all python processes
                $pythonProcs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
                
                # Check for pip running (either as pip.exe or python -m pip)
                $pipProcs = Get-CimInstance Win32_Process -Filter "Name='pip.exe'" -ErrorAction SilentlyContinue
                if ($pipProcs) {
                    $serviceRunning = $true
                }
                
                # Also check for python running pip (python -m pip install ...)
                if (-not $serviceRunning) {
                    foreach ($proc in $pythonProcs) {
                        if ($proc.CommandLine -and ($proc.CommandLine -like "*pip*install*" -or $proc.CommandLine -like "*-m pip*")) {
                            $serviceRunning = $true
                            break
                        }
                    }
                }
                
                # Check for python with specific command line pattern (main.py, start_services.py)
                if (-not $serviceRunning -and $CommandLinePattern) {
                    foreach ($proc in $pythonProcs) {
                        if ($proc.CommandLine -and $proc.CommandLine -like "*$CommandLinePattern*") {
                            $serviceRunning = $true
                            break
                        }
                    }
                }
                
                # Check for npm/node processes (for Frontend)
                if (-not $serviceRunning) {
                    $npmProcs = Get-CimInstance Win32_Process -Filter "Name='npm.exe' OR Name='npm.cmd'" -ErrorAction SilentlyContinue
                    if ($npmProcs) {
                        $serviceRunning = $true
                    }
                }
                
                if (-not $serviceRunning) {
                    $nodeProcs = Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue
                    foreach ($proc in $nodeProcs) {
                        # Check if node is running vite or npm
                        if ($proc.CommandLine -and ($proc.CommandLine -like "*vite*" -or $proc.CommandLine -like "*npm*" -or $proc.CommandLine -like "*5173*")) {
                            $serviceRunning = $true
                            break
                        }
                    }
                }
                
                if (-not $serviceRunning) {
                    # No matching process running and port not listening = crashed or user closed terminal
                    Write-Host ""
                    Write-Host ""
                    Write-Host "========================================" -ForegroundColor Red
                    Write-Host "  ERROR: $ServiceName CRASHED" -ForegroundColor Red
                    Write-Host "========================================" -ForegroundColor Red
                    Write-Host ""
                    Write-Host "  No process is listening on port $Port." -ForegroundColor Red
                    Write-Host "  Check the $ServiceName terminal for error messages." -ForegroundColor Yellow
                    Write-Host ""
                    return $false
                }
                # else: process still running (pip or python with matching command), keep waiting
            }
        }
        
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Host "`r  [$elapsed s] $ServiceName is healthy!                              " -ForegroundColor Green
                return $true
            }
        } catch {
            # Service not ready yet, continue waiting
        }
        
        Write-Host "`r  [$elapsed s] Waiting for $ServiceName...                    " -NoNewline -ForegroundColor Gray
        Start-Sleep -Seconds $IntervalSeconds
        $elapsed += $IntervalSeconds
    }
}

# Build proxy commands for child terminals
$proxyCommands = ""
if ($httpProxy) {
    $proxyCommands += "`$env:http_proxy='$httpProxy'; `$env:HTTP_PROXY='$httpProxy'; "
}
if ($httpsProxy) {
    $proxyCommands += "`$env:https_proxy='$httpsProxy'; `$env:HTTPS_PROXY='$httpsProxy'; "
}
if ($noProxy) {
    $proxyCommands += "`$env:no_proxy='$noProxy'; `$env:NO_PROXY='$noProxy'; "
}

# ============================================================================
# FRONTEND LAUNCH MODE (browser dev server vs Electron desktop app)
# ============================================================================
# In Electron mode the frontend terminal runs `npm run electron:dev`, which
# starts the Vite dev server on 5173 and opens the Electron window pointed at
# it. The runtime binary is downloaded lazily the first time `electron` runs,
# and that download uses @electron/get's own proxy vars. We set them for the
# whole frontend terminal so both npm and the first-launch download go through
# the proxy.
$frontendProxyCommands = ""
if ($Electron) {
    $frontendStartCommand = "npm run electron:dev"
    $frontendHeader = "FRONTEND UI (ELECTRON DESKTOP APP)"
    $frontendStartMsg = "Starting Electron desktop app (dev server on port 5173)..."
    $frontendTitle = "Electron"

    $electronProxy = if ($httpsProxy) { $httpsProxy } elseif ($httpProxy) { $httpProxy } else { "" }
    if ($electronProxy) {
        $frontendProxyCommands = $proxyCommands +
            "`$env:ELECTRON_GET_USE_PROXY='true'; `$env:GLOBAL_AGENT_HTTPS_PROXY='$electronProxy'; `$env:GLOBAL_AGENT_HTTP_PROXY='$electronProxy'; "
    }
} else {
    $frontendStartCommand = "npm run dev -- --host 0.0.0.0 --port 5173"
    $frontendHeader = "FRONTEND UI"
    $frontendStartMsg = "Starting Frontend (port 5173)..."
    $frontendTitle = "Frontend"
}

if ($IsWindowsOS) {
    $wtExists = if ($NoWindowsTerminal) { $false } else { Get-Command wt -ErrorAction SilentlyContinue }

    # ========================================================================
    # TERMINAL 1: BACKEND (with paddleocr check)
    # ========================================================================
    if ($script:skipBackend) {
        Write-Host "Skipping Backend (already running on port 8000)" -ForegroundColor Yellow
    } else {
        Write-Host "Launching Terminal 1: Backend..." -ForegroundColor Yellow
        
        
        $backendScript = @"
`$ErrorActionPreference = 'Continue'
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

# Set proxy
$proxyCommands

Write-Host '========================================' -ForegroundColor Cyan
Write-Host '  BACKEND SERVICE' -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''

`$parentDir = Split-Path '$ScriptDir' -Parent
Set-Location `$parentDir
Write-Host "Working directory: `$PWD" -ForegroundColor Gray
Write-Host ''

# Check if venv exists and is valid
`$venvPath = '.\smartclassroom'
`$venvValid = (Test-Path "`$venvPath\Scripts\Activate.ps1") -and (Test-Path "`$venvPath\Scripts\python.exe")

if (-not `$venvValid) {
    # Remove broken/partial venv if exists
    if (Test-Path `$venvPath) {
        Write-Host 'Removing incomplete smartclassroom venv...' -ForegroundColor Yellow
        Remove-Item -Path `$venvPath -Recurse -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    
    Write-Host 'Creating smartclassroom virtual environment...' -ForegroundColor Yellow
    python -m venv `$venvPath
    if (`$LASTEXITCODE -ne 0) {
        Write-Host 'Failed to create virtual environment!' -ForegroundColor Red
        Write-Host 'Try running: Remove-Item -Path smartclassroom -Recurse -Force' -ForegroundColor Yellow
        Read-Host 'Press Enter to close'
        exit 1
    }
}

Write-Host 'Activating virtual environment...' -ForegroundColor Gray
& "`$venvPath\Scripts\Activate.ps1"

Set-Location '$ScriptDir'
Write-Host "Changed to: `$PWD" -ForegroundColor Gray

Write-Host ''
Write-Host 'Starting Backend Service (port 8000)...' -ForegroundColor Green
Write-Host ''
python main.py
"@
    $backendEncoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($backendScript))

    if ($wtExists) {
        Start-Process wt -ArgumentList "-w SmartClassroom new-tab --title Backend powershell -NoExit -EncodedCommand $backendEncoded"
    } else {
        Invoke-WmiMethod -Path win32_process -Name create -ArgumentList "powershell.exe -ExecutionPolicy Bypass -EncodedCommand $backendEncoded" | Out-Null
    }

    Write-Host "  Backend terminal launched" -ForegroundColor Green
    Write-Host ""
    }  # End of skipBackend check
    
    # Wait for Backend to be healthy before starting Content Search
    $backendHealthy = Wait-ForService -ServiceName "Backend" -Url "http://localhost:8000/health" -Port 8000 -CommandLinePattern "main.py"
    if (-not $backendHealthy) {
        Write-Host "Exiting script due to Backend startup failure." -ForegroundColor Red
        exit 1
    }
    
    # ========================================================================
    # TERMINAL 2: CONTENT SEARCH
    # ========================================================================
    if ($script:skipContentSearch) {
        Write-Host ""
        Write-Host "Skipping Content Search (already running on port 9011)" -ForegroundColor Yellow
    } else {
        Write-Host ""
        Write-Host "Launching Terminal 2: Content Search..." -ForegroundColor Yellow
        
        $contentSearchScript = @"
`$ErrorActionPreference = 'Continue'
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

# Set proxy
$proxyCommands

Write-Host '========================================' -ForegroundColor Cyan
Write-Host '  CONTENT SEARCH SERVICE' -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''

Set-Location '$ScriptDir\content_search'
Write-Host "Working directory: `$PWD" -ForegroundColor Gray
Write-Host ''

# Check if venv exists and is valid
`$venvPath = '.\venv_content_search'
`$venvValid = (Test-Path "`$venvPath\Scripts\Activate.ps1") -and (Test-Path "`$venvPath\Scripts\python.exe")

if (-not `$venvValid) {
    # Remove broken/partial venv if exists
    if (Test-Path `$venvPath) {
        Write-Host 'Removing incomplete venv_content_search...' -ForegroundColor Yellow
        Remove-Item -Path `$venvPath -Recurse -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    
    Write-Host 'Creating venv_content_search virtual environment...' -ForegroundColor Yellow
    python -m venv `$venvPath
    if (`$LASTEXITCODE -ne 0) {
        Write-Host 'Failed to create virtual environment!' -ForegroundColor Red
        Write-Host 'Try running: Remove-Item -Path venv_content_search -Recurse -Force' -ForegroundColor Yellow
        Read-Host 'Press Enter to close'
        exit 1
    }
}

Write-Host 'Activating virtual environment...' -ForegroundColor Gray
& "`$venvPath\Scripts\Activate.ps1"

Write-Host ''
Write-Host 'Starting Content Search Service (port 9011)...' -ForegroundColor Green
Write-Host ''
python .\start_services.py
"@
    $contentSearchEncoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($contentSearchScript))

    if ($wtExists) {
        Start-Process wt -ArgumentList "-w SmartClassroom new-tab --title ContentSearch powershell -NoExit -EncodedCommand $contentSearchEncoded"
    } else {
        Invoke-WmiMethod -Path win32_process -Name create -ArgumentList "powershell.exe -ExecutionPolicy Bypass -EncodedCommand $contentSearchEncoded" | Out-Null
    }

    Write-Host "  Content Search terminal launched" -ForegroundColor Green
    Write-Host ""
    }  # End of skipContentSearch check
    
    # Wait for Content Search to be healthy before starting Frontend
    $csHealthy = Wait-ForService -ServiceName "Content Search" -Url "http://localhost:9011/api/v1/system/health" -Port 9011 -DependentPorts @(8000) -CommandLinePattern "start_services.py"
    if (-not $csHealthy) {
        Write-Host "Exiting script due to Content Search startup failure." -ForegroundColor Red
        exit 1
    }
    
    # ========================================================================
    # TERMINAL 3: FRONTEND
    # ========================================================================
    if ($script:skipFrontend) {
        Write-Host ""
        Write-Host "Skipping Frontend (already running on port 5173)" -ForegroundColor Yellow
    } else {
        Write-Host ""
        Write-Host "Launching Terminal 3: $frontendTitle..." -ForegroundColor Yellow

        $frontendScript = @"
`$ErrorActionPreference = 'Continue'

# Set proxy for Electron download (if applicable)
$frontendProxyCommands

Write-Host '========================================' -ForegroundColor Cyan
Write-Host '  $frontendHeader' -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''

Set-Location '$ScriptDir\ui'
Write-Host "Working directory: `$PWD" -ForegroundColor Gray
Write-Host ''

Write-Host 'Installing npm dependencies...' -ForegroundColor Yellow
npm install

Write-Host ''
Write-Host '$frontendStartMsg' -ForegroundColor Green
Write-Host ''
$frontendStartCommand
"@
    $frontendEncoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($frontendScript))

    if ($wtExists) {
        Start-Process wt -ArgumentList "-w SmartClassroom new-tab --title $frontendTitle powershell -NoExit -EncodedCommand $frontendEncoded"
    } else {
        Invoke-WmiMethod -Path win32_process -Name create -ArgumentList "powershell.exe -ExecutionPolicy Bypass -EncodedCommand $frontendEncoded" | Out-Null
    }

    Write-Host "  $frontendTitle terminal launched" -ForegroundColor Green
    Write-Host ""
    }  # End of skipFrontend check
    
    # Wait for Frontend to be healthy
    $frontendHealthy = Wait-ForService -ServiceName "Frontend" -Url "http://localhost:5173" -Port 5173 -DependentPorts @(8000, 9011) -CommandLinePattern "npm"
    if (-not $frontendHealthy) {
        Write-Host "Exiting script due to Frontend startup failure." -ForegroundColor Red
        exit 1
    }
}

# ============================================================================
# COMPLETION MESSAGE
# ============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   ALL SERVICES ARE HEALTHY!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Services:" -ForegroundColor Yellow
Write-Host "  1. Backend        -> http://localhost:8000  [HEALTHY]" -ForegroundColor White
Write-Host "  2. Content Search -> http://localhost:9011  [HEALTHY]" -ForegroundColor White
if ($Electron) {
    Write-Host "  3. Frontend       -> Electron desktop app (dev server http://localhost:5173)  [HEALTHY]" -ForegroundColor White
    Write-Host ""
    Write-Host "The Smart Classroom Electron window should now be open." -ForegroundColor Cyan
    Write-Host "(You can also open http://localhost:5173 in a browser.)" -ForegroundColor DarkGray
} else {
    Write-Host "  3. Frontend       -> http://localhost:5173  [HEALTHY]" -ForegroundColor White
    Write-Host ""
    Write-Host "Open in browser: http://localhost:5173" -ForegroundColor Cyan
}
Write-Host ""

if ($Silent) {
    Write-Host "Silent mode: services started successfully. Exiting..." -ForegroundColor Green
    Write-Host ""
    $script:servicesStarted = $false  # Prevent trap from stopping services
    exit 0
} else {
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "  Press 'Q' to stop all services and exit" -ForegroundColor Yellow
    Write-Host "  Press 'E' to exit (keep services running)" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host ""

    # Wait for user input to stop services or exit
    while ($true) {
        $key = Read-Host "Enter choice (Q/E)"
        switch ($key.ToUpper()) {
            "Q" {
                Stop-AllServices
                for ($i = 30; $i -gt 0; $i--) {
                    Start-Sleep -Seconds 1
                }
                exit 0
            }
            "E" {
                Write-Host ""
                Write-Host "  Exiting. Services will continue running in their terminals." -ForegroundColor Green
                Write-Host "  Close the terminal windows manually to stop services." -ForegroundColor Gray
                Write-Host ""
                $script:servicesStarted = $false  # Prevent trap from stopping services
                exit 0
            }
        }
    }
}