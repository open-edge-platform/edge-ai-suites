# start.ps1 - Start the content_search backend and Flutter Windows app together.
# Run from the utils/flutter directory:
#   cd education-ai-suite\utils\flutter
#   .\start.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Smart Classroom - Startup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# --- Resolve paths ------------------------------------------------------------
# Use $PSScriptRoot when available; fall back to the script's own path.
$ScriptDir        = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path $MyInvocation.MyCommand.Path -Parent }
$RepoRoot         = (Get-Item (Join-Path $ScriptDir "..\..")).FullName
$ContentSearchDir = Join-Path $RepoRoot "smart-classroom\content_search"
$VenvPython       = Join-Path $ContentSearchDir "venv_content_search\Scripts\python.exe"
$StartServices    = Join-Path $ContentSearchDir "start_services.py"

Write-Host "  Repo root   : $RepoRoot" -ForegroundColor DarkGray
Write-Host "  Backend dir : $ContentSearchDir" -ForegroundColor DarkGray
Write-Host "  Python venv : $VenvPython" -ForegroundColor DarkGray

# --- Sanity checks ------------------------------------------------------------
if (-not (Test-Path $VenvPython)) {
    Write-Error "Python venv not found at '$VenvPython'. Run .\setup.ps1 first."
    exit 1
}

if (-not (Test-Path $StartServices)) {
    Write-Error "start_services.py not found at '$StartServices'."
    exit 1
}

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    Write-Error "Flutter not found in PATH. Install from https://docs.flutter.dev/get-started/install/windows"
    exit 1
}

# --- 1. Start content_search backend in a new window -------------------------
Write-Host ""
Write-Host "Starting content_search backend services..." -ForegroundColor Green
$BackendProc = Start-Process -FilePath $VenvPython `
    -ArgumentList "`"$StartServices`"" `
    -WorkingDirectory $ContentSearchDir `
    -PassThru

Write-Host "  Backend started (PID $($BackendProc.Id))." -ForegroundColor White

# --- 2. Wait briefly so ChromaDB / main_app begin initialising ----------------
Write-Host ""
Write-Host "Waiting 5 seconds for backend to begin initialising..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# --- 3. Start Flutter Windows app (blocks in this window) --------------------
Write-Host ""
Write-Host "Launching Flutter Windows app..." -ForegroundColor Green
Write-Host "  (Close this window or press Ctrl+C to stop everything)" -ForegroundColor DarkGray
Write-Host ""

try {
    Push-Location $ScriptDir
    flutter run -d windows
} finally {
    Pop-Location

    # --- 4. Tear down the backend when Flutter exits --------------------------
    Write-Host ""
    Write-Host "Flutter exited. Stopping backend (PID $($BackendProc.Id))..." -ForegroundColor Yellow
    if (-not $BackendProc.HasExited) {
        $prevPref = $ErrorActionPreference
        $ErrorActionPreference = 'SilentlyContinue'
        taskkill /F /T /PID $BackendProc.Id 2>&1 | Out-Null
        $ErrorActionPreference = $prevPref
    }
    Write-Host "Done." -ForegroundColor Green
}
