#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Smart Classroom Unified Startup Script (Windows & Linux)
.DESCRIPTION
    Launches the Smart Classroom application with all required services:
    1. Backend Python service (port 8000) - includes paddleocr if OCR enabled
    2. Content Search service (port 9011) - includes install.ps1 setup
    3. Frontend UI (port 5173)
.NOTES
    Terminals launch sequentially: Backend -> Content Search -> Frontend
#>

param(
    [switch]$SkipProxy,
    [switch]$Help
)

if ($Help) {
    Write-Host @"
Smart Classroom Startup Script

Usage: ./start-smart-classroom.ps1 [-SkipProxy] [-Help]

Options:
    -SkipProxy    Skip proxy configuration prompts
    -Help         Show this help message

Services Launched (in order):
    1. Backend (port 8000)     - Main Python pipeline service (with paddleocr if OCR enabled)
    2. Content Search (9011)   - RAG, video summarization, semantic search
    3. Frontend (port 5173)    - React UI

"@ -ForegroundColor Cyan
    exit 0
}

# ============================================================================
# PLATFORM DETECTION
# ============================================================================
$IsWindowsOS = $IsWindows -or ($PSVersionTable.PSVersion.Major -lt 6) -or ($env:OS -eq "Windows_NT")
$IsLinuxOS = $IsLinux -or ($PSVersionTable.Platform -eq "Unix")

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   SMART CLASSROOM STARTUP SCRIPT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Platform: $(if ($IsWindowsOS) { 'Windows' } else { 'Linux' })" -ForegroundColor Yellow
Write-Host "PowerShell: $($PSVersionTable.PSVersion)" -ForegroundColor Yellow
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
# STEP 1: PROXY CONFIGURATION
# ============================================================================
Write-Host ""
Write-Host "[1/4] PROXY CONFIGURATION" -ForegroundColor Green
Write-Host "-------------------------" -ForegroundColor Green

$httpProxy = ""
$httpsProxy = ""
$noProxy = ""

if (-not $SkipProxy) {
    Write-Host ""
    Write-Host "Enter proxy settings (leave blank to skip):" -ForegroundColor Yellow
    Write-Host ""
    
    $httpProxy = Read-Host "HTTP_PROXY  (e.g., http://proxy-iind.intel.com:912)"
    $httpsProxy = Read-Host "HTTPS_PROXY (e.g., http://proxy-iind.intel.com:912)"
    $noProxy = Read-Host "NO_PROXY    (e.g., localhost,127.0.0.1,::)"
    
    if ($httpProxy) {
        $env:HTTP_PROXY = $httpProxy
        $env:http_proxy = $httpProxy
        Write-Host "  Set HTTP_PROXY=$httpProxy" -ForegroundColor Gray
    }
    
    if ($httpsProxy) {
        $env:HTTPS_PROXY = $httpsProxy
        $env:https_proxy = $httpsProxy
        Write-Host "  Set HTTPS_PROXY=$httpsProxy" -ForegroundColor Gray
    }
    
    if ($noProxy) {
        $env:NO_PROXY = $noProxy
        $env:no_proxy = $noProxy
        Write-Host "  Set NO_PROXY=$noProxy" -ForegroundColor Gray
    }
    
    if (-not $httpProxy -and -not $httpsProxy -and -not $noProxy) {
        Write-Host "  No proxy configured (direct connection)" -ForegroundColor Gray
    }
} else {
    Write-Host "  Skipped (using existing environment)" -ForegroundColor Gray
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

$ocrEnabled = $false
$configPath = Join-Path $ScriptDir "config.yaml"
if (Test-Path $configPath) {
    $configContent = Get-Content $configPath -Raw
    if ($configContent -match "ocr:\s*\n\s*enabled:\s*true") {
        $ocrEnabled = $true
        Write-Host "  OCR: Enabled (will install paddleocr)" -ForegroundColor Yellow
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
Write-Host "Terminals will launch sequentially:" -ForegroundColor Yellow
Write-Host "  1. Backend (port 8000)" -ForegroundColor White
Write-Host "  2. Content Search (port 9011)" -ForegroundColor White
Write-Host "  3. Frontend (port 5173)" -ForegroundColor White
Write-Host ""

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

if ($IsWindowsOS) {
    $wtExists = Get-Command wt -ErrorAction SilentlyContinue
    
    # ========================================================================
    # TERMINAL 1: BACKEND (with paddleocr check)
    # ========================================================================
    Write-Host "Launching Terminal 1: Backend..." -ForegroundColor Yellow
    
    # Build paddleocr install command if OCR enabled
    $paddleocrCmd = ""
    if ($ocrEnabled) {
        $paddleocrCmd = @"

Write-Host ''
Write-Host 'Installing PaddleOCR (OCR enabled in config)...' -ForegroundColor Yellow
pip install paddleocr==2.7.0.3 --no-deps
"@
    }
    
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

# Check if venv exists
`$venvPath = '.\smartclassroom'
if (-not (Test-Path "`$venvPath\Scripts\Activate.ps1")) {
    Write-Host 'Creating smartclassroom virtual environment...' -ForegroundColor Yellow
    python -m venv `$venvPath
    if (`$LASTEXITCODE -ne 0) {
        Write-Host 'Failed to create virtual environment!' -ForegroundColor Red
        Read-Host 'Press Enter to close'
        exit 1
    }
}

Write-Host 'Activating virtual environment...' -ForegroundColor Gray
& "`$venvPath\Scripts\Activate.ps1"

Set-Location '$ScriptDir'
Write-Host "Changed to: `$PWD" -ForegroundColor Gray

Write-Host ''
Write-Host 'Upgrading pip and installing requirements...' -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install --upgrade -r requirements.txt
$paddleocrCmd

Write-Host ''
Write-Host 'Starting Backend Service (port 8000)...' -ForegroundColor Green
Write-Host ''
python main.py
"@
    $backendEncoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($backendScript))
    
    if ($wtExists) {
        Start-Process wt -ArgumentList "-w SmartClassroom new-tab --title Backend powershell -NoExit -EncodedCommand $backendEncoded"
    } else {
        Start-Process powershell -ArgumentList "-NoExit", "-EncodedCommand", $backendEncoded
    }
    
    Write-Host "  Backend terminal launched" -ForegroundColor Green
    Write-Host "  Waiting 5 seconds before launching Content Search..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
    
    # ========================================================================
    # TERMINAL 2: CONTENT SEARCH
    # ========================================================================
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

# Check if venv exists
`$venvPath = '.\venv_content_search'
if (-not (Test-Path "`$venvPath\Scripts\Activate.ps1")) {
    Write-Host 'Creating venv_content_search virtual environment...' -ForegroundColor Yellow
    python -m venv `$venvPath
    if (`$LASTEXITCODE -ne 0) {
        Write-Host 'Failed to create virtual environment!' -ForegroundColor Red
        Read-Host 'Press Enter to close'
        exit 1
    }
}

Write-Host 'Activating virtual environment...' -ForegroundColor Gray
& "`$venvPath\Scripts\Activate.ps1"

# Run install.ps1 if tesseract not found
`$tesseractExists = Get-Command tesseract -ErrorAction SilentlyContinue
if (-not `$tesseractExists) {
    Write-Host ''
    Write-Host 'Running install.ps1 (Content Search dependencies)...' -ForegroundColor Yellow
    Write-Host 'NOTE: This requires Administrator privileges' -ForegroundColor Yellow
    Write-Host ''
    if (Test-Path '.\install.ps1') {
        & '.\install.ps1'
    } else {
        Write-Host 'install.ps1 not found, skipping...' -ForegroundColor Yellow
    }
}

Write-Host ''
Write-Host 'Upgrading pip and installing requirements...' -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host ''
Write-Host 'Starting Content Search Service (port 9011)...' -ForegroundColor Green
Write-Host ''
python .\start_services.py
"@
    $contentSearchEncoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($contentSearchScript))
    
    if ($wtExists) {
        Start-Process wt -ArgumentList "-w SmartClassroom new-tab --title ContentSearch powershell -NoExit -EncodedCommand $contentSearchEncoded"
    } else {
        Start-Process powershell -ArgumentList "-NoExit", "-EncodedCommand", $contentSearchEncoded
    }
    
    Write-Host "  Content Search terminal launched" -ForegroundColor Green
    Write-Host "  Waiting 5 seconds before launching Frontend..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
    
    # ========================================================================
    # TERMINAL 3: FRONTEND
    # ========================================================================
    Write-Host ""
    Write-Host "Launching Terminal 3: Frontend..." -ForegroundColor Yellow
    
    $frontendScript = @"
`$ErrorActionPreference = 'Continue'

Write-Host '========================================' -ForegroundColor Cyan
Write-Host '  FRONTEND UI' -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''

Set-Location '$ScriptDir\ui'
Write-Host "Working directory: `$PWD" -ForegroundColor Gray
Write-Host ''

Write-Host 'Installing npm dependencies...' -ForegroundColor Yellow
npm install

Write-Host ''
Write-Host 'Starting Frontend (port 5173)...' -ForegroundColor Green
Write-Host ''
npm run dev -- --host 0.0.0.0 --port 5173
"@
    $frontendEncoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($frontendScript))
    
    if ($wtExists) {
        Start-Process wt -ArgumentList "-w SmartClassroom new-tab --title Frontend powershell -NoExit -EncodedCommand $frontendEncoded"
    } else {
        Start-Process powershell -ArgumentList "-NoExit", "-EncodedCommand", $frontendEncoded
    }
    
    Write-Host "  Frontend terminal launched" -ForegroundColor Green
    
} else {
    # ========== LINUX ==========
    Write-Host "Linux support - launching terminals..." -ForegroundColor Cyan
    
    $gnomeExists = Get-Command gnome-terminal -ErrorAction SilentlyContinue
    $konsoleExists = Get-Command konsole -ErrorAction SilentlyContinue
    $xtermExists = Get-Command xterm -ErrorAction SilentlyContinue
    
    $terminalCmd = if ($gnomeExists) { "gnome-terminal" }
                   elseif ($konsoleExists) { "konsole" }
                   elseif ($xtermExists) { "xterm" }
                   else { $null }
    
    if (-not $terminalCmd) {
        Write-Host "No supported terminal found. Run manually:" -ForegroundColor Red
        Write-Host ""
        Write-Host "Terminal 1 (Backend):" -ForegroundColor Cyan
        Write-Host "  cd $(Split-Path $ScriptDir -Parent) && python -m venv smartclassroom && source smartclassroom/bin/activate && cd smart-classroom && pip install -r requirements.txt && python main.py"
        Write-Host ""
        Write-Host "Terminal 2 (Content Search):" -ForegroundColor Cyan
        Write-Host "  cd $ScriptDir/content_search && python -m venv venv_content_search && source venv_content_search/bin/activate && pip install -r requirements.txt && python start_services.py"
        Write-Host ""
        Write-Host "Terminal 3 (Frontend):" -ForegroundColor Cyan
        Write-Host "  cd $ScriptDir/ui && npm install && npm run dev -- --host 0.0.0.0 --port 5173"
        exit 1
    }
    
    # Build proxy export for bash
    $proxyExport = ""
    if ($httpProxy) { $proxyExport += "export http_proxy='$httpProxy'; export HTTP_PROXY='$httpProxy'; " }
    if ($httpsProxy) { $proxyExport += "export https_proxy='$httpsProxy'; export HTTPS_PROXY='$httpsProxy'; " }
    if ($noProxy) { $proxyExport += "export no_proxy='$noProxy'; export NO_PROXY='$noProxy'; " }
    
    # Terminal 1: Backend
    Write-Host "Launching Terminal 1: Backend..." -ForegroundColor Yellow
    $paddleCmd = if ($ocrEnabled) { "pip install paddleocr==2.7.0.3 --no-deps; " } else { "" }
    $parentDir = Split-Path $ScriptDir -Parent
    $be_bash = @"
$proxyExport
cd '$parentDir'
echo '========================================'
echo '  BACKEND SERVICE'
echo '========================================'
if [ ! -f 'smartclassroom/bin/activate' ]; then
    echo 'Creating virtual environment...'
    python3 -m venv smartclassroom
fi
source smartclassroom/bin/activate
cd smart-classroom
pip install --upgrade pip
pip install -r requirements.txt
$paddleCmd
echo 'Starting Backend (port 8000)...'
python main.py
exec bash
"@
    
    if ($terminalCmd -eq "gnome-terminal") {
        Start-Process gnome-terminal -ArgumentList "--title=Backend", "--", "bash", "-c", $be_bash
    } elseif ($terminalCmd -eq "konsole") {
        Start-Process konsole -ArgumentList "--new-tab", "-p", "tabtitle=Backend", "-e", "bash", "-c", $be_bash
    } else {
        Start-Process xterm -ArgumentList "-title", "Backend", "-e", "bash", "-c", $be_bash
    }
    
    Start-Sleep -Seconds 5
    
    # Terminal 2: Content Search
    Write-Host "Launching Terminal 2: Content Search..." -ForegroundColor Yellow
    $cs_bash = @"
$proxyExport
cd '$ScriptDir/content_search'
echo '========================================'
echo '  CONTENT SEARCH SERVICE'
echo '========================================'
if [ ! -f 'venv_content_search/bin/activate' ]; then
    echo 'Creating virtual environment...'
    python3 -m venv venv_content_search
fi
source venv_content_search/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo 'Starting Content Search (port 9011)...'
python start_services.py
exec bash
"@
    
    if ($terminalCmd -eq "gnome-terminal") {
        Start-Process gnome-terminal -ArgumentList "--title=ContentSearch", "--", "bash", "-c", $cs_bash
    } elseif ($terminalCmd -eq "konsole") {
        Start-Process konsole -ArgumentList "--new-tab", "-p", "tabtitle=ContentSearch", "-e", "bash", "-c", $cs_bash
    } else {
        Start-Process xterm -ArgumentList "-title", "ContentSearch", "-e", "bash", "-c", $cs_bash
    }
    
    Start-Sleep -Seconds 5
    
    # Terminal 3: Frontend
    Write-Host "Launching Terminal 3: Frontend..." -ForegroundColor Yellow
    $fe_bash = @"
cd '$ScriptDir/ui'
echo '========================================'
echo '  FRONTEND UI'
echo '========================================'
npm install
echo 'Starting Frontend (port 5173)...'
npm run dev -- --host 0.0.0.0 --port 5173
exec bash
"@
    
    if ($terminalCmd -eq "gnome-terminal") {
        Start-Process gnome-terminal -ArgumentList "--title=Frontend", "--", "bash", "-c", $fe_bash
    } elseif ($terminalCmd -eq "konsole") {
        Start-Process konsole -ArgumentList "--new-tab", "-p", "tabtitle=Frontend", "-e", "bash", "-c", $fe_bash
    } else {
        Start-Process xterm -ArgumentList "-title", "Frontend", "-e", "bash", "-c", $fe_bash
    }
}

# ============================================================================
# COMPLETION MESSAGE
# ============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   ALL TERMINALS LAUNCHED" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor Yellow
Write-Host "  1. Backend        -> http://localhost:8000" -ForegroundColor White
Write-Host "  2. Content Search -> http://localhost:9011" -ForegroundColor White
Write-Host "  3. Frontend       -> http://localhost:5173" -ForegroundColor White
Write-Host ""
Write-Host "Wait for all services to initialize, then open:" -ForegroundColor Green
Write-Host "  http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "To verify Content Search health:" -ForegroundColor Gray
if ($IsWindowsOS) {
    Write-Host '  Invoke-RestMethod -Uri "http://127.0.0.1:9011/api/v1/system/health"' -ForegroundColor DarkGray
} else {
    Write-Host '  curl http://127.0.0.1:9011/api/v1/system/health' -ForegroundColor DarkGray
}
Write-Host ""
Write-Host "Press Ctrl+C in each terminal to stop services." -ForegroundColor Yellow
Write-Host ""
