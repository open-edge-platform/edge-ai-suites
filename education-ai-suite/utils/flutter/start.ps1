# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

<#
.SYNOPSIS
    Start Smart Classroom RAG application
.DESCRIPTION
    Launches the Content Search backend in a separate window
    and starts the Flutter Windows app.
#>

Write-Host "`n=== Starting Smart Classroom RAG ===" -ForegroundColor Cyan



# Check prerequisites
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$venvPython = Join-Path $repoRoot "venv_content_search\Scripts\python.exe"
$backendScript = Join-Path $repoRoot "smart-classroom\content_search\start_services.py"

if (-not (Test-Path $venvPython)) {
    Write-Host "[X] Python venv not found. Run .\setup.ps1 first" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $PSScriptRoot "pubspec.yaml"))) {
    Write-Host "[X] Flutter app not set up. Run .\setup.ps1 first" -ForegroundColor Red
    exit 1
}

# Start backend in separate window
Write-Host "`nStarting Content Search backend..." -ForegroundColor Yellow
Write-Host "  Backend will launch in a separate window" -ForegroundColor Gray
$backendCmd = "Set-Location '$repoRoot'; & '$venvPython' '$backendScript'; Read-Host 'Backend stopped - press Enter to close'"

Start-Process powershell.exe `
    -ArgumentList "-NoExit", "-Command", $backendCmd `
    -WorkingDirectory $repoRoot

Write-Host "[OK] Backend window opened" -ForegroundColor Green

# Wait for backend to be fully ready
Write-Host "`nWaiting for backend to be fully healthy..." -ForegroundColor Yellow
Write-Host "  This ensures backend is completely ready before launching Flutter" -ForegroundColor Gray
Write-Host "  Checking health endpoint: http://127.0.0.1:9011/api/v1/system/health" -ForegroundColor Gray

$deadline = (Get-Date).AddSeconds(20)
$backendReady = $false
$attempts = 0

do {
    Start-Sleep -Seconds 1
    $attempts++
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:9011/api/v1/system/health" `
                                       -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Host "`n[OK] Backend is fully healthy and ready (after $attempts seconds)" -ForegroundColor Green
            $backendReady = $true
            break
        }
    } catch {
        Write-Host "." -NoNewline
    }
} while ((Get-Date) -lt $deadline)

if (-not $backendReady) {
    Write-Host "`n`n[X] Backend failed to become healthy within 60 seconds" -ForegroundColor Red
    Write-Host "  Check the backend window for error messages" -ForegroundColor Yellow
    Write-Host "  Common issues:" -ForegroundColor Yellow
    Write-Host "    - Port 9011 already in use" -ForegroundColor Gray
    Write-Host "    - Missing dependencies (run .\utils\flutter\setup.ps1)" -ForegroundColor Gray
    Write-Host "    - Python environment issues" -ForegroundColor Gray
    Write-Host "`nExiting without launching Flutter..." -ForegroundColor Red
    exit 1
}

# Start Flutter app in separate window
Write-Host "`nBackend is ready - now starting Flutter app..." -ForegroundColor Yellow
Write-Host "  Flutter will launch in a separate window" -ForegroundColor Gray

$flutterCmd = "Set-Location '$PSScriptRoot'; flutter run -d windows; Write-Host '`nFlutter app closed' -ForegroundColor Cyan; Read-Host 'Press Enter to close this window'"

Start-Process powershell.exe `
    -ArgumentList "-NoExit", "-Command", $flutterCmd `
    -WorkingDirectory $PSScriptRoot

Write-Host "[OK] Flutter window opened" -ForegroundColor Green
Write-Host "`n=== Startup Complete ===" -ForegroundColor Cyan
Write-Host "Both services are running in separate windows:" -ForegroundColor Green
Write-Host "  - Backend: Content Search service on port 9011" -ForegroundColor Gray
Write-Host "  - Flutter: Smart Classroom app" -ForegroundColor Gray
Write-Host "`nYou can now use commands like 'upload a file'" -ForegroundColor Yellow
Write-Host "Remember to close both windows when done" -ForegroundColor Yellow
