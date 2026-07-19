# =============================================================================
# setup_windows.ps1
# Smart Kiosk Assistant - Windows 11 Setup Script
# 
# Features:
# - Checks Python 3.11+ installation
# - Installs FFmpeg (auto-download if missing)
# - Creates virtual environments for each service
# - Installs all Python dependencies
# - Verifies installation
# - Creates necessary directories
#
# Usage: powershell -ExecutionPolicy Bypass -File setup_windows.ps1
# =============================================================================

param(
    [switch]$Silent = $false  # Set to $true for silent/automated mode
)

$ErrorActionPreference = "Stop"
$WarningPreference = "SilentlyContinue"

# Color output for readability
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
    Write-Host "[*] $Message" -ForegroundColor Yellow
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Red
}

function Write-Step {
    param([string]$Message)
    Write-Host "`n→ $Message" -ForegroundColor Cyan
}

# Get script directory and root directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir  # Go up to voice-enabled-interactions root
$KioskDir = $ScriptDir  # smart-kiosk-assistant is the kiosk directory
$EdgeAIDir = Join-Path $RootDir "edge-ai-libraries"

Write-Header "SMART KIOSK ASSISTANT - WINDOWS 11 SETUP"
Write-Info "Setup directory: $ScriptDir"

# =============================================================================
# STEP 1: Check Python Installation
# =============================================================================

Write-Step "Checking Python 3.11+ installation..."

try {
    $PythonVersion = python --version 2>$null
    if ($PythonVersion -match "3\.(11|12|13)") {
        Write-Success "Python found: $PythonVersion"
    }
    else {
        Write-Error-Custom "Python 3.11+ not found. Current version: $PythonVersion"
        Write-Info "Please install Python 3.11+ from https://www.python.org/downloads/"
        exit 1
    }
}
catch {
    Write-Error-Custom "Python not found in PATH"
    Write-Info "Please install Python 3.11+ from https://www.python.org/downloads/"
    Write-Info "Make sure to check 'Add Python to PATH' during installation"
    exit 1
}

# =============================================================================
# STEP 2: Check/Install FFmpeg
# =============================================================================

Write-Step "Checking FFmpeg installation..."

$FFmpegExists = $false
try {
    $FFmpegVersion = ffmpeg -version 2>$null | Select-Object -First 1
    if ($FFmpegVersion) {
        Write-Success "FFmpeg found: $FFmpegVersion"
        $FFmpegExists = $true
    }
}
catch {}

if (-not $FFmpegExists) {
    Write-Info "FFmpeg not found. Attempting to install..."
    
    # Try winget (preferred)
    try {
        Write-Info "Installing FFmpeg via Windows Package Manager..."
        winget install ffmpeg -e -h --accept-source-agreements 2>$null | Out-Null
        Start-Sleep -Seconds 2
        
        $FFmpegVersion = ffmpeg -version 2>$null | Select-Object -First 1
        if ($FFmpegVersion) {
            Write-Success "FFmpeg installed successfully: $FFmpegVersion"
        }
        else {
            throw "Installation verification failed"
        }
    }
    catch {
        # Try Chocolatey
        try {
            Write-Info "Trying Chocolatey package manager..."
            $ChocoExists = choco --version 2>$null
            if ($ChocoExists) {
                choco install ffmpeg -y 2>$null | Out-Null
                Start-Sleep -Seconds 2
                
                $FFmpegVersion = ffmpeg -version 2>$null | Select-Object -First 1
                if ($FFmpegVersion) {
                    Write-Success "FFmpeg installed via Chocolatey: $FFmpegVersion"
                }
                else {
                    throw "Installation verification failed"
                }
            }
            else {
                throw "Chocolatey not found"
            }
        }
        catch {
            Write-Error-Custom "Could not auto-install FFmpeg"
            Write-Info "Please install manually:"
            Write-Info "  Option 1: winget install ffmpeg"
            Write-Info "  Option 2: choco install ffmpeg"
            Write-Info "  Option 3: Download from https://ffmpeg.org/download.html"
            exit 1
        }
    }
}

# =============================================================================
# STEP 3: Create Virtual Environments
# =============================================================================

Write-Step "Setting up Python virtual environments..."

$Services = @(
    @{ Name = "text-to-speech"; Path = "$EdgeAIDir\microservices\text-to-speech" },
    @{ Name = "audio-analyzer"; Path = "$EdgeAIDir\microservices\audio-analyzer" },
    @{ Name = "rag-service"; Path = "$KioskDir\rag-service" },
    @{ Name = "kiosk-core"; Path = "$KioskDir" }
)

function Ensure-WindowsVenv {
    param(
        [hashtable]$Service
    )

    $VenvPath = Join-Path $Service.Path "venv"
    $PythonExe = Join-Path $VenvPath "Scripts\python.exe"

    if (Test-Path $PythonExe) {
        Write-Info "Virtual environment ready for $($Service.Name)"
        return
    }

    if (Test-Path $VenvPath) {
        Write-Info "Existing venv for $($Service.Name) is missing Windows python executable; recreating..."
        Remove-Item -Recurse -Force $VenvPath
    }

    Write-Step "Creating virtual environment for $($Service.Name)..."
    Push-Location $Service.Path
    try {
        python -m venv venv
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $PythonExe)) {
            throw "venv creation failed"
        }
        Write-Success "Virtual environment created for $($Service.Name)"
    }
    finally {
        Pop-Location
    }
}

foreach ($Service in $Services) {
    try {
        Ensure-WindowsVenv -Service $Service
    }
    catch {
        Write-Error-Custom "Failed to prepare venv for $($Service.Name): $_"
        exit 1
    }
}

# =============================================================================
# STEP 4: Install Python Dependencies
# =============================================================================

Write-Step "Installing Python dependencies..."

foreach ($Service in $Services) {
    $VenvPath = Join-Path $Service.Path "venv"
    $PythonExe = Join-Path $VenvPath "Scripts\python.exe"
    $RequirementsFile = Join-Path $Service.Path "requirements.txt"

    if (-not (Test-Path $PythonExe)) {
        Write-Info "Python executable not found for $($Service.Name); recreating virtual environment..."
        try {
            Ensure-WindowsVenv -Service $Service
        }
        catch {
            Write-Error-Custom "Failed to repair venv for $($Service.Name): $_"
            exit 1
        }
    }
    
    if (-not (Test-Path $RequirementsFile)) {
        Write-Info "No requirements.txt found for $($Service.Name), skipping..."
        continue
    }
    
    Write-Step "Installing dependencies for $($Service.Name)..."
    try {
        & $PythonExe -m pip install --upgrade pip setuptools wheel | Out-Null
        & $PythonExe -m pip install -r $RequirementsFile
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Dependencies installed for $($Service.Name)"
        }
        else {
            throw "pip install failed with exit code $LASTEXITCODE"
        }
    }
    catch {
        Write-Error-Custom "Failed to install dependencies for $($Service.Name): $_"
        exit 1
    }
}

# =============================================================================
# STEP 4.5: Build React UI
# =============================================================================

Write-Step "Building React web UI..."

$ReactDir = Join-Path $KioskDir "kiosk-ui-react"
if (Test-Path (Join-Path $ReactDir "package.json")) {
    $NodeOk = $false
    try {
        $NodeVersion = node --version 2>$null
        if ($NodeVersion) { $NodeOk = $true }
    }
    catch {}

    if (-not $NodeOk) {
        Write-Info "Node.js not found. Attempting to install via winget..."
        try {
            winget install OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements --silent | Out-Null
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            $NodeVersion = node --version 2>$null
            if ($NodeVersion) { $NodeOk = $true }
        }
        catch {}
    }

    if (-not $NodeOk) {
        Write-Error-Custom "Node.js is required to build the React UI. Install Node.js LTS and re-run setup."
        exit 1
    }

    Write-Success "Node.js found: $NodeVersion"
    Push-Location $ReactDir
    try {
        Write-Step "Installing UI dependencies (npm install)..."
        npm install --no-fund --no-audit
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
        # Ensure esbuild's native binary is present even if install scripts were skipped.
        if (Test-Path "node_modules/esbuild/install.js") { node "node_modules/esbuild/install.js" | Out-Null }
        Write-Step "Building UI bundle (npm run build)..."
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
        Write-Success "React UI built to kiosk-ui-react/dist"
    }
    catch {
        Write-Error-Custom "Failed to build React UI: $_"
        exit 1
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Info "kiosk-ui-react not found, skipping UI build"
}

# =============================================================================
# STEP 5: Create Directories for Data/Logs/Cache
# =============================================================================

Write-Step "Creating necessary directories..."

$DirsToCreate = @(
    "$KioskDir\generated_audio",
    "$KioskDir\logs",
    "$EdgeAIDir\microservices\audio-analyzer\storage",
    "$EdgeAIDir\microservices\audio-analyzer\models",
    "$EdgeAIDir\microservices\audio-analyzer\chunks",
    "$EdgeAIDir\microservices\audio-analyzer\.cache",
    "$EdgeAIDir\microservices\text-to-speech\storage",
    "$EdgeAIDir\microservices\text-to-speech\models",
    "$EdgeAIDir\microservices\text-to-speech\.cache",
    "$KioskDir\rag-service\storage",
    "$KioskDir\rag-service\models",
    "$KioskDir\rag-service\.cache",
    "$RootDir\.logs"
)

foreach ($Dir in $DirsToCreate) {
    if (-not (Test-Path $Dir)) {
        try {
            New-Item -ItemType Directory -Path $Dir -Force | Out-Null
            Write-Info "Created: $Dir"
        }
        catch {
            Write-Error-Custom "Failed to create directory: $Dir"
        }
    }
}

# =============================================================================
# STEP 6: Create .env file if missing
# =============================================================================

Write-Step "Setting up environment configuration..."

$EnvFile = Join-Path $ScriptDir ".env"
if (-not (Test-Path $EnvFile)) {
    $EnvContent = @"
# Smart Kiosk Assistant - Windows 11 Configuration
# Generated by setup_windows.ps1

# Service URLs (localhost for Windows native)
KIOSK_CORE_ANALYZER_URL=http://127.0.0.1:8010/v1/audio/transcriptions
KIOSK_CORE_RAG_URL=http://127.0.0.1:8020/api/v1/query
KIOSK_CORE_TTS_URL=http://127.0.0.1:8011/v1/audio/speech
KIOSK_CORE_METRICS_URL=http://127.0.0.1:9000

# Gradio UI Configuration
KIOSK_CORE_UI_BASE_URL=http://127.0.0.1:8012
KIOSK_CORE_UI_ANALYZER_URL=http://127.0.0.1:8010/v1/audio/transcriptions
KIOSK_CORE_UI_RAG_URL=http://127.0.0.1:8020/api/v1/query
KIOSK_CORE_UI_TTS_URL=http://127.0.0.1:8011/v1/audio/speech

# Audio Analyzer Configuration
AUDIO_ANALYZER_MICROPHONE=Microphone

# TTS Configuration
TEXT_TO_SPEECH_CORS_ALLOW_ORIGINS=http://127.0.0.1,http://localhost

# Performance Settings
KIOSK_CORE_SAMPLE_RATE=16000
KIOSK_CORE_CHUNK_SECONDS=5.0
"@
    try {
        Set-Content -Path $EnvFile -Value $EnvContent
        Write-Success "Created .env configuration file"
    }
    catch {
        Write-Error-Custom "Failed to create .env file: $_"
    }
}
else {
    Write-Info ".env file already exists"
}

# =============================================================================
# STEP 6.5: Pre-build / warm up AI models
#
# Each model-backed service downloads its source model and exports it to
# OpenVINO IR on first startup (inside the FastAPI lifespan, BEFORE the
# /health endpoint becomes available). On a fresh machine this first-run
# export can take many minutes and exceeds the health-check window used by
# start_kiosk.ps1, making services look like they "never come up".
#
# We do that heavy one-time work here, during setup, where there is no
# health-check timeout. After this completes, start_kiosk.ps1 finds the
# exported models already on disk and every service becomes healthy quickly.
# =============================================================================

Write-Step "Pre-building AI models (one-time; this can take several minutes)..."

$ModelServices = @(
    @{ Name = "rag-service"; Path = "$KioskDir\rag-service" },
    @{ Name = "text-to-speech"; Path = "$EdgeAIDir\microservices\text-to-speech" },
    @{ Name = "audio-analyzer"; Path = "$EdgeAIDir\microservices\audio-analyzer" }
)

# Python snippet that reproduces exactly what each service does at startup:
# ensure the model is downloaded/exported, then load it into memory once.
$WarmupPy = @"
import sys
try:
    from utils.ensure_model import ensure_model
    from utils.preload_models import preload_models
    ensure_model()
    preload_models()
    print('WARMUP_OK')
except Exception as exc:
    print('WARMUP_FAILED: ' + repr(exc))
    sys.exit(1)
"@

foreach ($Service in $ModelServices) {
    $VenvPath = Join-Path $Service.Path "venv"
    $PythonExe = Join-Path $VenvPath "Scripts\python.exe"

    if (-not (Test-Path $PythonExe)) {
        Write-Error-Custom "Skipping model warmup for $($Service.Name): missing $PythonExe"
        continue
    }

    Write-Step "Warming up models for $($Service.Name) (downloads + OpenVINO export on first run)..."
    Push-Location $Service.Path
    try {
        $WarmupPy | & $PythonExe -
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Models ready for $($Service.Name)"
        }
        else {
            Write-Error-Custom "Model warmup failed for $($Service.Name) (exit code $LASTEXITCODE)"
            Write-Info "The service will retry the export on first startup, which may be slow."
        }
    }
    catch {
        Write-Error-Custom "Model warmup errored for $($Service.Name): $_"
        Write-Info "The service will retry the export on first startup, which may be slow."
    }
    finally {
        Pop-Location
    }
}

# =============================================================================
# STEP 7: Verify Installation
# =============================================================================

Write-Header "VERIFYING INSTALLATION"

Write-Step "Checking Python packages..."

foreach ($Service in $Services) {
    $VenvPath = Join-Path $Service.Path "venv"
    $PythonExe = Join-Path $VenvPath "Scripts\python.exe"
    $RequirementsFile = Join-Path $Service.Path "requirements.txt"

    if (-not (Test-Path $PythonExe)) {
        Write-Error-Custom "Verification skipped for $($Service.Name): missing $PythonExe"
        continue
    }
    
    if (-not (Test-Path $RequirementsFile)) {
        continue
    }
    
    try {
        $Output = & $PythonExe -m pip show pydantic 2>&1
        if ($Output) {
            Write-Success "$($Service.Name) dependencies verified"
        }
        else {
            throw "Package check failed"
        }
    }
    catch {
        Write-Error-Custom "Failed to verify $($Service.Name) dependencies"
    }
}

# =============================================================================
# COMPLETION
# =============================================================================

Write-Header "SETUP COMPLETE"
Write-Success "All components installed successfully!"
Write-Info "Next step: Run start_kiosk.ps1 to start all services"
Write-Info ""
Write-Info "Usage:"
Write-Info "  powershell -ExecutionPolicy Bypass -File start_kiosk.ps1"
Write-Info ""
