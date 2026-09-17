# =============================================================================
# uninstall_ata.ps1
# AI Teaching Assistant - Uninstall Script
#
# Removes the Python virtual environments (venv) and the downloaded models,
# storage, and cache folders for all services. The application has no
# installer, so this fully "uninstalls" it while leaving the source tree intact.
#
# WARNING: Deleting the storage/ folders permanently removes user data,
# including the RAG vector database of ingested course materials
# (rag-service/storage/vector_db). Back up anything you want to keep first.
#
# Usage: powershell -ExecutionPolicy Bypass -File uninstall_ata.ps1
#        powershell -ExecutionPolicy Bypass -File uninstall_ata.ps1 -Yes
#        powershell -ExecutionPolicy Bypass -File uninstall_ata.ps1 -Yes -RemoveHfCache
# =============================================================================

param(
    [switch]$Yes = $false,            # Skip the confirmation prompt
    [switch]$RemoveHfCache = $false   # Also delete the Hugging Face cache in the user profile
)

$ErrorActionPreference = "Continue"
$WarningPreference = "SilentlyContinue"

# Color output
function Write-Header {
    param([string]$Message)
    Write-Host "`n" -ForegroundColor White
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
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

# Resolve paths relative to this script so it works from any working directory.
$RootDir = $PSScriptRoot

Write-Header "AI TEACHING ASSISTANT - UNINSTALL"

# Service directories (relative to the ai-teaching-assistant root). The
# kiosk-core service has only a venv; its models/storage/.cache folders do not
# exist and are skipped automatically.
$ServiceDirs = @(
    "edge-ai-libraries\microservices\audio-analyzer",
    "edge-ai-libraries\microservices\text-to-speech",
    "voice-enabled-interactions\smart-kiosk-assistant\rag-service",
    "voice-enabled-interactions\smart-kiosk-assistant"
)

$Folders = @("venv", "models", "storage", ".cache")

# Build the list of folders that actually exist so we can preview them.
$Targets = @()
foreach ($ServiceDir in $ServiceDirs) {
    foreach ($Folder in $Folders) {
        $Path = Join-Path $RootDir (Join-Path $ServiceDir $Folder)
        if (Test-Path $Path) {
            $Targets += $Path
        }
    }
}

if ($Targets.Count -eq 0) {
    Write-Info "Nothing to remove - no venv, models, storage, or .cache folders found."
    Write-Success "Already uninstalled."
    return
}

Write-Info "The following folders will be permanently deleted:"
foreach ($Path in $Targets) {
    Write-Host "    $Path" -ForegroundColor Gray
}

Write-Host ""
Write-Error-Custom "This removes downloaded models AND user data (RAG vector database)."

if (-not $Yes) {
    $Answer = Read-Host "Type 'yes' to continue"
    if ($Answer -ne "yes") {
        Write-Info "Uninstall cancelled. No changes were made."
        return
    }
}

Write-Header "REMOVING FILES"

$RemovedCount = 0
foreach ($Path in $Targets) {
    try {
        Remove-Item -Recurse -Force $Path -ErrorAction Stop
        Write-Success "Removed $Path"
        $RemovedCount++
    }
    catch {
        Write-Error-Custom "Could not remove $Path : $($_.Exception.Message)"
    }
}

if ($RemoveHfCache) {
    $HfCache = Join-Path $env:USERPROFILE ".cache\huggingface"
    if (Test-Path $HfCache) {
        try {
            Remove-Item -Recurse -Force $HfCache -ErrorAction Stop
            Write-Success "Removed $HfCache"
            $RemovedCount++
        }
        catch {
            Write-Error-Custom "Could not remove $HfCache : $($_.Exception.Message)"
        }
    }
    else {
        Write-Info "No Hugging Face cache found at $HfCache"
    }
}

Write-Header "UNINSTALL COMPLETE"
Write-Success "Removed $RemovedCount folder(s)"
Write-Info "To reinstall, run: powershell -ExecutionPolicy Bypass -File setup_windows.ps1"
Write-Host ""
