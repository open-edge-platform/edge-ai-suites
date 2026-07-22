# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

<#
.SYNOPSIS
    Smart Classroom RAG Flutter setup
.DESCRIPTION
    Performs complete setup: configures proxy, verifies Flutter SDK and Python,
    installs Flutter dependencies, creates Python venv, installs backend requirements,
    and creates .env configuration.
#>

# Open in new window if not already running in one
if (-not $env:SETUP_NEW_WINDOW) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "& { `$env:SETUP_NEW_WINDOW='1'; & '$PSCommandPath' }"
    Write-Host "Opening setup in new window (admin mode)..." -ForegroundColor Yellow
    return
}

Write-Host "`n=== Smart Classroom RAG Setup ===" -ForegroundColor Cyan

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

# Create Python venv
Write-Host "`nCreating Python virtual environment..." -ForegroundColor Yellow
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$contentSearchPath = Join-Path $repoRoot "smart-classroom\content_search"
$venvPath = Join-Path $contentSearchPath "venv_content_search"

if (-not (Test-Path $venvPath)) {
    python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X] Failed to create Python venv" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Python venv created at $venvPath" -ForegroundColor Green
} else {
    Write-Host "[OK] Python venv already exists" -ForegroundColor Green
}

# Install backend dependencies
Write-Host "`nUpgrading pip..." -ForegroundColor Yellow
$pipPath = Join-Path $venvPath "Scripts\pip.exe"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"

& $pythonPath -m pip install --upgrade pip

if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Failed to upgrade pip" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Pip upgraded" -ForegroundColor Green

Write-Host "`nInstalling backend dependencies..." -ForegroundColor Yellow
$requirementsPath = Join-Path $repoRoot "smart-classroom\content_search\requirements.txt"

& $pipPath install -r $requirementsPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Failed to install backend dependencies" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Backend dependencies installed" -ForegroundColor Green

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
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Run .\start.ps1 to start the application" -ForegroundColor White
Write-Host "  2. Or use 'sc-up' skill" -ForegroundColor White
