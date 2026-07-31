<#
.SYNOPSIS
    Smart Classroom RAG Flutter setup
.DESCRIPTION
    Performs complete setup: configures proxy, verifies Flutter SDK and Python,
    installs Flutter dependencies, creates Python venv, installs backend requirements,
    and creates .env configuration.
#>

Write-Host "`n=== Smart Classroom RAG Setup ===" -ForegroundColor Cyan
# Check Flutter's config.yaml for content_search settings
Write-Host "`nChecking Flutter configuration..." -ForegroundColor Yellow
$configPath = Join-Path $PSScriptRoot "config.yaml"

if (Test-Path $configPath) {
    Write-Host "[OK] Flutter config.yaml found" -ForegroundColor Green
    try {
        $configContent = Get-Content $configPath -Raw
        # Check if content_search is enabled
        if ($configContent -match 'content_search:\s*\{\s*enabled:\s*true\s*\}') {
            Write-Host "[OK] Content Search is enabled" -ForegroundColor Green
        } else {
            Write-Host "[X] Content Search is DISABLED in Flutter config.yaml" -ForegroundColor Red
            Write-Host "    Please enable it by changing:" -ForegroundColor Yellow
            Write-Host "    content_search: { enabled: false }" -ForegroundColor Gray
            Write-Host "    to:" -ForegroundColor Yellow
            Write-Host "    content_search: { enabled: true }" -ForegroundColor Green
            exit 1
        }
        # Check if qa is enabled
        if ($configContent -match 'qa:\s*\{\s*enabled:\s*true\s*\}') {
            Write-Host "[OK] Q&A is enabled" -ForegroundColor Green
        } else {
            Write-Host "[!] Warning: Q&A feature is disabled" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[!] Warning: Could not parse config.yaml" -ForegroundColor Yellow
    }
} else {
    Write-Host "[X] Flutter config.yaml not found at $configPath" -ForegroundColor Red
    Write-Host "    A config.yaml should exist in utils/flutter/" -ForegroundColor Yellow
    Write-Host "    Copy it from smart-classroom/config.yaml and enable only content_search & qa" -ForegroundColor Yellow
    exit 1
}
# Check prerequisites
Write-Host "`nChecking prerequisites..." -ForegroundColor Yellow

try {
    $flutterVersion = flutter --version 2>&1 | Select-String "Flutter"
    Write-Host "[OK] Flutter SDK found: $flutterVersion" -ForegroundColor Green
} catch {
    Write-Host "[X] Flutter SDK not found in PATH" -ForegroundColor Red
    Write-Host "Install Flutter from: https://docs.flutter.dev/get-started/install/windows" -ForegroundColor Yellow
    exit 1
}

try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[X] Python not found in PATH" -ForegroundColor Red
    exit 1
}

# Setup Flutter
Write-Host "`nSetting up Flutter dependencies..." -ForegroundColor Yellow
Push-Location $PSScriptRoot

flutter config --enable-windows-desktop
flutter create --platforms windows,web .
flutter pub get

if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Flutter setup failed" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "[OK] Flutter dependencies installed" -ForegroundColor Green
Pop-Location

# Determine repository root (parent of utils/)
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

# Create Python venv for main backend
Write-Host "`nCreating Python virtual environment for main backend..." -ForegroundColor Yellow
$mainVenvPath = Join-Path $repoRoot "smartclassroom"
$smartClassroomPath = Join-Path $repoRoot "smart-classroom"

if (-not (Test-Path $mainVenvPath)) {
    python -m venv $mainVenvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X] Failed to create main backend venv" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Main backend venv created at $mainVenvPath" -ForegroundColor Green
} else {
    Write-Host "[OK] Main backend venv already exists" -ForegroundColor Green
}

# Install main backend dependencies
Write-Host "`nUpgrading pip for main backend..." -ForegroundColor Yellow
$mainPipPath = Join-Path $mainVenvPath "Scripts\pip.exe"
$mainPythonPath = Join-Path $mainVenvPath "Scripts\python.exe"

& $mainPythonPath -m pip install --upgrade pip

if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Failed to upgrade pip for main backend" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Pip upgraded for main backend" -ForegroundColor Green

Write-Host "`nInstalling main backend dependencies..." -ForegroundColor Yellow
Write-Host "  Includes: VLM, OCR, ASR, and core components" -ForegroundColor Gray
Write-Host "  This may take 10-15 minutes on first run..." -ForegroundColor Gray
$mainRequirementsPath = Join-Path $smartClassroomPath "requirements.txt"

& $mainPipPath install -r $mainRequirementsPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Failed to install main backend dependencies" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Main backend dependencies installed" -ForegroundColor Green

# Create Python venv for content search backend
Write-Host "`nCreating Python virtual environment for content search..." -ForegroundColor Yellow
Write-Host "  Note: main.py auto-starts content search using this venv when enabled" -ForegroundColor Gray
$contentSearchPath = Join-Path $smartClassroomPath "content_search"
$contentSearchVenvPath = Join-Path $contentSearchPath "venv_content_search"

if (-not (Test-Path $contentSearchVenvPath)) {
    python -m venv $contentSearchVenvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X] Failed to create content search venv" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Content search venv created at $contentSearchVenvPath" -ForegroundColor Green
} else {
    Write-Host "[OK] Content search venv already exists" -ForegroundColor Green
}

# Install content search dependencies
Write-Host "`nUpgrading pip for content search..." -ForegroundColor Yellow
$contentSearchPipPath = Join-Path $contentSearchVenvPath "Scripts\pip.exe"
$contentSearchPythonPath = Join-Path $contentSearchVenvPath "Scripts\python.exe"

& $contentSearchPythonPath -m pip install --upgrade pip

if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Failed to upgrade pip for content search" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Pip upgraded for content search" -ForegroundColor Green

Write-Host "`nInstalling content search dependencies..." -ForegroundColor Yellow
Write-Host "  Includes: RAG, ChromaDB, document processing" -ForegroundColor Gray
$contentSearchRequirementsPath = Join-Path $contentSearchPath "requirements.txt"

& $contentSearchPipPath install -r $contentSearchRequirementsPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Failed to install content search dependencies" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Content search dependencies installed" -ForegroundColor Green

# Create .env file
Write-Host "`nCreating configuration file..." -ForegroundColor Yellow
$envPath = Join-Path $PSScriptRoot "assets\.env"
$envDir = Split-Path -Parent $envPath

New-Item -ItemType Directory -Force -Path $envDir | Out-Null

@"
CONTENT_SEARCH_API_URL=http://127.0.0.1:9011
MAIN_API_URL=http://127.0.0.1:8000
"@ | Set-Content $envPath

Write-Host "[OK] Configuration created at assets\.env" -ForegroundColor Green

# Summary
Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host "Architecture:" -ForegroundColor Yellow
Write-Host "  - Main Backend (port 8000): VLM, OCR, ASR, core services" -ForegroundColor Gray
Write-Host "  - Content Search (port 9011): RAG, Q&A, file management (auto-started)" -ForegroundColor Gray
Write-Host "  - Flutter App: Cross-platform UI" -ForegroundColor Gray
Write-Host "`nVirtual Environments:" -ForegroundColor Yellow
Write-Host "  - smartclassroom/ - Main backend dependencies" -ForegroundColor Gray
Write-Host "  - smart-classroom/content_search/venv_content_search/ - Content Search dependencies" -ForegroundColor Gray
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  Run: .\start.ps1" -ForegroundColor White
Write-Host "`nNote: Main backend automatically starts Content Search when content_search.enabled: true" -ForegroundColor Yellow
