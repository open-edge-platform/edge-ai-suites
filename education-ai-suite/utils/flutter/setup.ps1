# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

<#
.SYNOPSIS
    Launcher for Smart Classroom RAG Flutter setup
.DESCRIPTION
    Opens a new PowerShell window to perform setup with proper environment inheritance.
    This ensures proxy and system settings are correctly applied.
#>

Write-Host "`nLaunching Smart Classroom Setup in a new window..." -ForegroundColor Cyan
Write-Host "The setup will run in a separate PowerShell window with proper environment." -ForegroundColor Yellow
Write-Host "Please wait for the setup to complete in that window." -ForegroundColor Yellow

$workerScript = Join-Path $PSScriptRoot "setup-worker.ps1"
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path $workerScript)) {
    Write-Host "[X] setup-worker.ps1 not found at $workerScript" -ForegroundColor Red
    exit 1
}

# Launch setup worker in new PowerShell window
Start-Process powershell.exe `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$workerScript`"" `
    -WorkingDirectory $repoRoot `
    -Wait

Write-Host "`n[OK] Setup process completed. Check the setup window for results." -ForegroundColor Green
