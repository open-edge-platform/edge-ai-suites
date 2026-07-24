# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# One-command way to run the long-context validator. Reuses the exact same
# backend venv and activation convention as setup-smart-classroom.ps1 /
# start-smart-classroom.ps1 (../smartclassroom, sibling of smart-classroom/):
# creates it via setup_env.ps1 if it doesn't exist yet, activates it the same
# way start-smart-classroom.ps1 activates it for the main backend, then runs
# validate_long_context.py from the smart-classroom/ working directory.
#
# Usage (any extra arguments are forwarded to validate_long_context.py):
#   .\components\llm\context_validation\run_validate_long_context.ps1
#   .\components\llm\context_validation\run_validate_long_context.ps1 --dry-run
#   .\components\llm\context_validation\run_validate_long_context.ps1 --models Qwen/Qwen3-8B --refine
#
# If PowerShell blocks the script with an UnauthorizedAccess/SecurityError:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $ScriptDir) { $ScriptDir = Get-Location }

# smart-classroom/ is 3 levels up from this script's directory
# (context_validation -> llm -> components -> smart-classroom).
$SmartClassroomRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path
$VenvPath = Join-Path (Split-Path $SmartClassroomRoot -Parent) "smartclassroom"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Backend venv not found at $VenvPath -- preparing it first (one-time; installing " -ForegroundColor Yellow -NoNewline
    Write-Host "requirements.txt can take several minutes) ..." -ForegroundColor Yellow
    & (Join-Path $ScriptDir "setup_env.ps1")
}

Write-Host "Activating backend venv ($VenvPath) ..." -ForegroundColor Gray
& (Join-Path $VenvPath "Scripts\Activate.ps1")

Set-Location $SmartClassroomRoot
python -m components.llm.context_validation.validate_long_context @ExtraArgs
exit $LASTEXITCODE
