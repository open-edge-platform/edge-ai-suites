# setup.ps1 - One-time setup for Smart Classroom RAG Flutter
# Run this script once from this directory before running the app.
#
# Usage:
#   cd education-ai-suite\utils\flutter
#   .\setup.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Flutter Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# ── 1. Check Flutter is installed ─────────────────────────────────────────────
if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    Write-Error @"
Flutter SDK not found in PATH.
Install from: https://docs.flutter.dev/get-started/install/windows
Then re-open this terminal and run setup.ps1 again.
"@
    exit 1
}

Write-Host ""
Write-Host "Flutter version:" -ForegroundColor Green
flutter --version

# --- 2. Enable Windows desktop target ----------------------------------------
Write-Host ""
Write-Host "Enabling Windows desktop support..." -ForegroundColor Green
flutter config --enable-windows-desktop | Out-Null

# --- 3. Generate platform-specific boilerplate --------------------------------
# flutter create . on an existing directory ONLY adds missing files.
# It will NOT overwrite lib/, pubspec.yaml, or assets/ that already exist.
Write-Host ""
Write-Host "Generating platform files (windows/, web/)..." -ForegroundColor Green
flutter create `
    --project-name smart_classroom `
    --org com.intel.smartclassroom `
    --platforms windows,web `
    .

# --- 4. Fetch pub dependencies ------------------------------------------------
Write-Host ""
Write-Host "Fetching dependencies (dio, riverpod, file_picker, dotenv)..." -ForegroundColor Green
flutter pub get

# --- 5. Set up content_search backend Python venv ----------------------------───
Write-Host ""
Write-Host "Setting up content_search backend Python environment..." -ForegroundColor Green

$ScriptDir        = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path $MyInvocation.MyCommand.Path -Parent }
$RepoRoot         = (Get-Item (Join-Path $ScriptDir "..\..")).FullName
$ContentSearchDir = Join-Path $RepoRoot "smart-classroom\content_search"
$VenvDir    = Join-Path $ContentSearchDir "venv_content_search"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $ContentSearchDir "requirements.txt"

if (-not (Test-Path $VenvDir)) {
    Write-Host "  Creating virtual environment at $VenvDir ..." -ForegroundColor White
    python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create Python virtual environment. Ensure Python 3.10+ is installed and in PATH."
        exit 1
    }
}

Write-Host "  Installing content_search requirements (this may take a few minutes)..." -ForegroundColor White
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -r $Requirements
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install failed. Check the error output above."
    exit 1
}

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  (Optional) Edit assets/.env to change the backend URL." -ForegroundColor Yellow
Write-Host ""
Write-Host "To start the app and backend together, run:" -ForegroundColor Yellow
Write-Host "  .\start.ps1" -ForegroundColor White
