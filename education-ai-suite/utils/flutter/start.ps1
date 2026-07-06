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

# Set proxy
$env:HTTP_PROXY  = "http://proxy-dmz.intel.com:911"
$env:HTTPS_PROXY = "http://proxy-dmz.intel.com:912"
$env:http_proxy  = "http://proxy-dmz.intel.com:911"
$env:https_proxy = "http://proxy-dmz.intel.com:912"
$env:NO_PROXY    = "localhost,127.0.0.1,::1,*.intel.com"
$env:no_proxy    = "localhost,127.0.0.1,::1,*.intel.com"

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
$backendCmd = "Set-Location '$repoRoot'; & '$venvPython' '$backendScript'; Read-Host 'Backend stopped - press Enter to close'"

Start-Process powershell.exe `
    -ArgumentList "-NoExit", "-Command", $backendCmd `
    -WorkingDirectory $repoRoot

Write-Host "[OK] Backend window opened" -ForegroundColor Green
Write-Host "  Wait for 'Application startup complete' message before using the app" -ForegroundColor Yellow

# Wait for backend to be ready
Write-Host "`nWaiting for backend to be ready..." -ForegroundColor Yellow
$deadline = (Get-Date).AddSeconds(60)
$backendReady = $false

do {
    Start-Sleep -Seconds 3
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:9011/api/v1/system/health" `
                                       -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Host "[OK] Backend is healthy" -ForegroundColor Green
            $backendReady = $true
            break
        }
    } catch {
        Write-Host "." -NoNewline
    }
} while ((Get-Date) -lt $deadline)

if (-not $backendReady) {
    Write-Host "`n⚠ Backend health check timed out" -ForegroundColor Yellow
    Write-Host "  Continuing anyway - check the backend window for errors" -ForegroundColor Yellow
}

# Start Flutter app
Write-Host "`nStarting Flutter app..." -ForegroundColor Yellow
Push-Location $PSScriptRoot

flutter run -d windows

Pop-Location

Write-Host "`n=== Application Closed ===" -ForegroundColor Cyan
Write-Host "Remember to close the backend window if still running" -ForegroundColor Yellow
