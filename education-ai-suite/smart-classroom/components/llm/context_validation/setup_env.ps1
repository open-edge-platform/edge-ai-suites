# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Prepares the Python environment validate_long_context.py needs (openvino-genai,
# transformers, optimum-intel, torch) WITHOUT running the full interactive
# setup-smart-classroom.ps1, which also sets up the frontend, content_search,
# and unrelated system-requirement checks.
#
# Creates/reuses the SAME backend venv setup-smart-classroom.ps1 creates
# ("smartclassroom", sibling of smart-classroom/) so this tool and the main app
# share one install of the OpenVINO/torch stack instead of duplicating several
# GB of packages. Running the full setup script later (or having already run
# it) is detected as "already exists" -- this script never conflicts with it.
#
# Usage (from smart-classroom/, or from anywhere -- paths are resolved
# relative to this script's own location):
#   .\components\llm\context_validation\setup_env.ps1
#
# If PowerShell blocks the script with an UnauthorizedAccess/SecurityError:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $ScriptDir) { $ScriptDir = Get-Location }

# smart-classroom/ is 3 levels up from this script's directory
# (context_validation -> llm -> components -> smart-classroom).
$SmartClassroomRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path
$VenvPath = Join-Path (Split-Path $SmartClassroomRoot -Parent) "smartclassroom"
$RequirementsPath = Join-Path $SmartClassroomRoot "requirements.txt"

if (-not (Test-Path $RequirementsPath)) {
    Write-Host "[ERROR] Could not find requirements.txt at $RequirementsPath" -ForegroundColor Red
    exit 1
}

if (Test-Path $VenvPath) {
    Write-Host "[OK] Backend venv already exists at $VenvPath" -ForegroundColor Green
} else {
    Write-Host "Creating backend venv at $VenvPath ..." -ForegroundColor Yellow
    python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create venv (is Python 3.12 on PATH?)" -ForegroundColor Red
        exit 1
    }
}

$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Expected venv python at $VenvPython but it's missing" -ForegroundColor Red
    exit 1
}

Write-Host "Installing $RequirementsPath into $VenvPython ..." -ForegroundColor Yellow
Write-Host "(This includes OpenVINO GenAI, transformers, and torch -- can take several minutes.)" -ForegroundColor Yellow
& $VenvPython -m pip install --upgrade pip --no-input
& $VenvPython -m pip install -r $RequirementsPath --no-input
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] pip install failed -- see output above" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[OK] Environment ready. Run the validator with:" -ForegroundColor Green
Write-Host "  & `"$VenvPython`" -m components.llm.context_validation.validate_long_context"
