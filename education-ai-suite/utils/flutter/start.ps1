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
$smartClassroomPath = Join-Path $repoRoot "smart-classroom"
$mainVenvPath = Join-Path $repoRoot "smartclassroom"
$mainPythonPath = Join-Path $mainVenvPath "Scripts\python.exe"
$mainScript = Join-Path $smartClassroomPath "main.py"

if (-not (Test-Path $mainPythonPath)) {
    Write-Host "[X] Main backend venv not found. Run .\setup.ps1 first" -ForegroundColor Red
    Write-Host "    Expected at: $mainVenvPath" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $mainScript)) {
    Write-Host "[X] main.py not found at: $mainScript" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $PSScriptRoot "pubspec.yaml"))) {
    Write-Host "[X] Flutter app not set up. Run .\setup.ps1 first" -ForegroundColor Red
    exit 1
}

# Check Flutter config exists
$flutterConfigPath = Join-Path $PSScriptRoot "config.yaml"
if (-not (Test-Path $flutterConfigPath)) {
    Write-Host "[X] Flutter config.yaml not found at $flutterConfigPath" -ForegroundColor Red
    Write-Host "    Run .\setup.ps1 first" -ForegroundColor Yellow
    exit 1
}

# Start main backend with Flutter config in background window
Write-Host "`nStarting backend with Flutter configuration..." -ForegroundColor Yellow
Write-Host "  Config: utils/flutter/config.yaml" -ForegroundColor Gray
Write-Host "  Port 8000: VLM service (warm start)" -ForegroundColor Gray
Write-Host "  Port 9011: Content Search (auto-started)" -ForegroundColor Gray
Write-Host "  Using venv: smartclassroom/" -ForegroundColor Gray
Write-Host "  Backend will run in a separate window" -ForegroundColor Gray

# Convert to relative path from smart-classroom directory
$relativeConfigPath = "..\\utils\\flutter\\config.yaml"

$mainCmd = "Set-Location '$smartClassroomPath'; `$env:SC_CONFIG_PATH='$relativeConfigPath'; & '$mainPythonPath' '$mainScript'"

Start-Process powershell.exe `
    -ArgumentList "-NoExit", "-Command", $mainCmd `
    -WorkingDirectory $smartClassroomPath

Write-Host "[OK] Main backend started in background" -ForegroundColor Green

# Wait for main backend with proper health checks
Write-Host "`nWaiting for main backend to become ready..." -ForegroundColor Yellow
Write-Host "  Backend (port 8000): VLM and core services" -ForegroundColor Gray
Write-Host "  Initial startup: 2-3 minutes (VLM model loading)" -ForegroundColor Gray

$maxWaitSeconds = 300  # 5 minutes total timeout
$startTime = Get-Date
$checkInterval = 5  # Check every 5 seconds

# Function to check if port is listening (not just bound)
function Test-ServiceListening {
    param([int]$Port)
    try {
        $connection = Get-NetTCPConnection -LocalPort $Port -State "Listen" -ErrorAction SilentlyContinue
        return $null -ne $connection
    } catch {
        return $false
    }
}

# Wait for backend to start listening
Write-Host "  Waiting for backend to start..." -ForegroundColor Gray
while (-not (Test-ServiceListening -Port 8000)) {
    $elapsed = ((Get-Date) - $startTime).TotalSeconds
    if ($elapsed -gt $maxWaitSeconds) {
        Write-Host "`n[X] Timeout: Backend did not start within 5 minutes" -ForegroundColor Red
        Write-Host "  Check the minimized backend window for errors" -ForegroundColor Yellow
        exit 1
    }
    Start-Sleep -Seconds $checkInterval
}
$backendStartTime = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)
Write-Host "  [OK] Backend is listening on port 8000 (after ${backendStartTime}s)" -ForegroundColor Green

# Wait for content search to start and become fully healthy
Write-Host "  Waiting for Content Search to become healthy..." -ForegroundColor Gray
$csHealthy = $false
while (-not $csHealthy) {
    $elapsed = ((Get-Date) - $startTime).TotalSeconds
    if ($elapsed -gt $maxWaitSeconds) {
        Write-Host "`n[!] Timeout: Content Search health did not reach 'ok' within ${maxWaitSeconds}s" -ForegroundColor Yellow
        Write-Host "    The app will launch anyway; the health banner will retry automatically." -ForegroundColor Gray
        break
    }
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:9011/api/v1/system/health" `
                                  -TimeoutSec 5 -ErrorAction Stop
        if ($resp.status -eq "ok") {
            $csHealthy = $true
        }
    } catch {}
    if (-not $csHealthy) { Start-Sleep -Seconds $checkInterval }
}
if ($csHealthy) {
    $csStartTime = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)
    Write-Host "  [OK] Content Search is healthy (after ${csStartTime}s)" -ForegroundColor Green
}

Write-Host "`n[OK] All backend services are ready!" -ForegroundColor Green
$totalTime = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)
Write-Host "  Total startup time: $totalTime seconds" -ForegroundColor Gray

# Start Flutter app in separate window
Write-Host "`nAll services ready - now starting Flutter app..." -ForegroundColor Yellow
Write-Host "  Flutter will launch in a separate window" -ForegroundColor Gray

$flutterCmd = "Set-Location '$PSScriptRoot'; flutter run -d windows; Write-Host '`nFlutter app closed' -ForegroundColor Cyan; Read-Host 'Press Enter to close this window'"

Start-Process powershell.exe `
    -ArgumentList "-NoExit", "-Command", $flutterCmd `
    -WorkingDirectory $PSScriptRoot

Write-Host "[OK] Flutter window opened" -ForegroundColor Green
Write-Host "`n=== Startup Complete ===" -ForegroundColor Cyan
Write-Host "All services are running:" -ForegroundColor Green
Write-Host "  - Backend (port 8000): VLM service [minimized window]" -ForegroundColor Gray
Write-Host "  - Content Search (port 9011): RAG API [auto-started by backend]" -ForegroundColor Gray
Write-Host "  - Flutter UI: Smart Classroom app [new window]" -ForegroundColor Gray
Write-Host "`nConfiguration: utils/flutter/config.yaml" -ForegroundColor Yellow
Write-Host "  Features enabled: content_search, qa" -ForegroundColor Gray
Write-Host "  All other features disabled" -ForegroundColor Gray
Write-Host "`nYou can now upload files and ask questions in the Flutter app" -ForegroundColor Yellow
Write-Host "To stop all services: close the backend window" -ForegroundColor Yellow
Write-Host "`nThis terminal can now be closed safely." -ForegroundColor Gray
