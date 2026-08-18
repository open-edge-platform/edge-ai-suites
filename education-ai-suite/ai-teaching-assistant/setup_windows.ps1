# =============================================================================
# setup_windows.ps1
# Smart Kiosk Assistant - Windows 11 Setup Script
# 
# Features:
# - Checks Python 3.11+ installation
# - Installs FFmpeg (auto-download if missing)
# - Creates virtual environments for each service
# - Installs all Python dependencies
# - Verifies installation
# - Creates necessary directories
#
# Usage: powershell -ExecutionPolicy Bypass -File setup_windows.ps1
# =============================================================================

param(
    [switch]$Silent = $false  # Set to $true for silent/automated mode
)

$ErrorActionPreference = "Stop"
$WarningPreference = "SilentlyContinue"

# PowerShell 7.4+ can promote native non-zero exits to PowerShell errors.
# Track whether this preference exists so wrappers can temporarily disable it.
$Script:HasPSNativeCommandUseErrorActionPreference = $null -ne (Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope Global -ErrorAction SilentlyContinue)

# Color output for readability
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

function Write-Step {
    param([string]$Message)
    Write-Host "`n-> $Message" -ForegroundColor Cyan
}

# Get script directory and root directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path   # ai-teaching-assistant (ATA) root
$RootDir = Split-Path -Parent $ScriptDir                       # edge-ai-suites (git superproject)
$EdgeAIDir = Join-Path $ScriptDir "edge-ai-libraries"          # submodule: TTS + audio-analyzer
$VeiDir = Join-Path $ScriptDir "voice-enabled-interactions"    # submodule: rag-service + kiosk_core
$KioskDir = Join-Path $VeiDir "smart-kiosk-assistant"          # kiosk-core (main.py) + rag-service

Write-Header "SMART KIOSK ASSISTANT - WINDOWS 11 SETUP"
Write-Info "Setup directory: $ScriptDir"

# =============================================================================
# STEP 0: Ensure edge-ai-libraries submodule (sparse checkout)
# =============================================================================

Write-Step "Ensuring edge-ai-libraries is available (git submodule, sparse)..."

# Only the microservices actually used by the kiosk are checked out to keep the
# clone small. Update this list if more components are needed later.
$SparsePaths = @(
    "microservices/audio-analyzer",
    "microservices/text-to-speech"
)

# Relative path of the submodule from the git superproject root. This matches the
# entry in the root .gitmodules (submodule.education-ai-suite/ai-teaching-assistant/edge-ai-libraries).
$SubmoduleRelPath = "education-ai-suite/ai-teaching-assistant/edge-ai-libraries"

# Upstream URL for the submodule. This is only a fallback used to register the
# submodule when the superproject's .gitmodules has no entry yet (e.g. a fresh
# checkout that never had the submodule added). When a .gitmodules entry exists,
# its URL takes precedence (see below) so new users always clone the source
# declared in .gitmodules rather than any hardcoded fork.
$SubmoduleUrl = "https://github.com/open-edge-platform/edge-ai-libraries.git"

# Locate the enclosing git repository (the edge-ai-suites fork).
$RepoRoot = $null
try {
    $RepoRoot = (git -C $RootDir rev-parse --show-toplevel 2>$null)
}
catch {}

$hasGit = $false
try { $null = git --version 2>$null; $hasGit = $true } catch {}

if (-not $hasGit) {
    Write-Error-Custom "git not found in PATH - cannot initialize the edge-ai-libraries submodule."
    Write-Info "Install Git for Windows from https://git-scm.com/download/win, then re-run this script."
    if (-not (Test-Path $EdgeAIDir)) { exit 1 }
    Write-Info "Continuing with the existing edge-ai-libraries directory at: $EdgeAIDir"
}
elseif ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    Write-Info "Not inside a git checkout - skipping submodule init."
    if (-not (Test-Path $EdgeAIDir)) {
        Write-Error-Custom "edge-ai-libraries not found at $EdgeAIDir and no git repo to initialize it from."
        exit 1
    }
    Write-Info "Using existing edge-ai-libraries directory at: $EdgeAIDir"
}
else {
    $RepoRoot = $RepoRoot.Trim()

    # Prefer the URL declared in the superproject's .gitmodules so a fresh clone
    # always pulls the source of truth instead of the hardcoded fallback above.
    $GitmodulesUrl = git -C $RepoRoot config --file .gitmodules --get "submodule.$SubmoduleRelPath.url" 2>$null
    if (-not [string]::IsNullOrWhiteSpace($GitmodulesUrl)) {
        $SubmoduleUrl = $GitmodulesUrl.Trim()
        Write-Info "Using submodule URL from .gitmodules: $SubmoduleUrl"
    }

    # git writes progress and (harmless) warnings to stderr. Under the script's
    # global "Stop" ErrorActionPreference, Windows PowerShell turns ANY native
    # stderr output into a terminating error, so relax it just for the git work
    # here and restore it afterwards.
    $SavedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'

    $SubmoduleAbs = Join-Path $RepoRoot $SubmoduleRelPath
    $SubmoduleGit = Join-Path $SubmoduleAbs ".git"

    if (-not (Test-Path $SubmoduleGit)) {
        # Mirror the manual workflow:
        #   git clone --depth 1 --filter=blob:none --sparse <url> <path>
        #   git -C <path> sparse-checkout set microservices/audio-analyzer microservices/text-to-speech
        # This keeps the checkout small (shallow history, blobs on demand, only the
        # required microservices in the working tree). git writes progress to stderr,
        # so 2>&1 | Out-Null is used (instead of 2>$null) to avoid tripping the
        # script's "Stop" ErrorActionPreference on non-error stderr output.
        if ((Test-Path $SubmoduleAbs) -and -not (Get-ChildItem -Force $SubmoduleAbs -ErrorAction SilentlyContinue)) {
            Remove-Item -Force $SubmoduleAbs -ErrorAction SilentlyContinue
        }
        Write-Info "Cloning submodule (shallow + partial + sparse)..."
        git clone --quiet --depth 1 --filter=blob:none --sparse $SubmoduleUrl $SubmoduleAbs 2>&1 | Out-Null
        if (Test-Path $SubmoduleGit) {
            git -C $SubmoduleAbs sparse-checkout set @SparsePaths 2>&1 | Out-Null
        }
    }

    if (Test-Path $SubmoduleGit) {
        # Ensure the sparse paths are applied (idempotent for pre-existing clones).
        Write-Info "Applying sparse-checkout paths: $($SparsePaths -join ', ')"
        git -C $SubmoduleAbs sparse-checkout set @SparsePaths 2>&1 | Out-Null

        # Promote the standalone sparse clone to a real submodule of the
        # superproject. `--force` reuses the clone already on disk instead of
        # re-downloading, and registers the .gitmodules entry + gitlink. Only do
        # this if the submodule is not already registered (check via git config,
        # which stays silent on a missing key so it never trips ErrorAction Stop).
        $null = git -C $RepoRoot config --file .gitmodules --get "submodule.$SubmoduleRelPath.url" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Info "Registering as git submodule..."
            git -c core.autocrlf=false -C $RepoRoot submodule add --force $SubmoduleUrl $SubmoduleRelPath 2>&1 | Out-Null
        }

        $ok = $true
        foreach ($p in $SparsePaths) {
            if (-not (Test-Path (Join-Path $SubmoduleAbs $p))) { $ok = $false }
        }
        $ErrorActionPreference = $SavedEAP
        if ($ok) {
            Write-Success "edge-ai-libraries submodule ready (sparse) at: $SubmoduleAbs"
        }
        else {
            Write-Error-Custom "Submodule checkout is missing expected microservice paths."
            exit 1
        }
    }
    else {
        $ErrorActionPreference = $SavedEAP
        Write-Error-Custom "Failed to clone the edge-ai-libraries submodule."
        Write-Info "Try manually: git clone --depth 1 --filter=blob:none --sparse `"$SubmoduleUrl`" `"$SubmoduleAbs`""
        exit 1
    }
}

# =============================================================================
# STEP 0b: Ensure voice-enabled-interactions submodule (sparse checkout)
# =============================================================================

Write-Step "Ensuring voice-enabled-interactions is available (git submodule, sparse)..."

# Only the two microservices actually used by the AI Teaching Assistant are
# checked out (rag-service + kiosk_core), plus the kiosk-core launcher and its
# requirements. This keeps the working tree small.
$VeiSparsePaths = @(
    "smart-kiosk-assistant/rag-service",
    "smart-kiosk-assistant/kiosk_core",
    "smart-kiosk-assistant/main.py",
    "smart-kiosk-assistant/requirements.txt"
)
$VeiSubmoduleRelPath = "education-ai-suite/ai-teaching-assistant/voice-enabled-interactions"
# Fallback URL only; when a .gitmodules entry exists its URL takes precedence
# (see below) so new users always clone the source declared in .gitmodules.
$VeiSubmoduleUrl = "https://github.com/intel-retail/voice-enabled-interactions.git"

$VeiRepoRoot = $null
try { $VeiRepoRoot = (git -C $ScriptDir rev-parse --show-toplevel 2>$null) } catch {}

if (-not $hasGit) {
    Write-Info "git not found - skipping voice-enabled-interactions submodule init."
    if (-not (Test-Path $KioskDir)) { Write-Error-Custom "voice-enabled-interactions not found at $KioskDir"; exit 1 }
}
elseif ([string]::IsNullOrWhiteSpace($VeiRepoRoot)) {
    Write-Info "Not inside a git checkout - skipping VEI submodule init."
    if (-not (Test-Path $KioskDir)) { Write-Error-Custom "voice-enabled-interactions not found at $KioskDir"; exit 1 }
}
else {
    $VeiRepoRoot = $VeiRepoRoot.Trim()

    # Prefer the URL declared in the superproject's .gitmodules so a fresh clone
    # always pulls the source of truth instead of the hardcoded fallback above.
    $VeiGitmodulesUrl = git -C $VeiRepoRoot config --file .gitmodules --get "submodule.$VeiSubmoduleRelPath.url" 2>$null
    if (-not [string]::IsNullOrWhiteSpace($VeiGitmodulesUrl)) {
        $VeiSubmoduleUrl = $VeiGitmodulesUrl.Trim()
        Write-Info "Using submodule URL from .gitmodules: $VeiSubmoduleUrl"
    }

    $SavedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'

    $VeiAbs = Join-Path $VeiRepoRoot $VeiSubmoduleRelPath
    $VeiGit = Join-Path $VeiAbs ".git"

    if (-not (Test-Path $VeiGit)) {
        if ((Test-Path $VeiAbs) -and -not (Get-ChildItem -Force $VeiAbs -ErrorAction SilentlyContinue)) {
            Remove-Item -Force $VeiAbs -ErrorAction SilentlyContinue
        }
        Write-Info "Cloning voice-enabled-interactions submodule (shallow + partial + sparse)..."
        git clone --quiet --depth 1 --filter=blob:none --sparse $VeiSubmoduleUrl $VeiAbs 2>&1 | Out-Null
        if (Test-Path $VeiGit) {
            git -C $VeiAbs sparse-checkout set --no-cone @VeiSparsePaths 2>&1 | Out-Null
        }
    }

    if (Test-Path $VeiGit) {
        Write-Info "Applying sparse-checkout paths: $($VeiSparsePaths -join ', ')"
        git -C $VeiAbs sparse-checkout set --no-cone @VeiSparsePaths 2>&1 | Out-Null

        $null = git -C $VeiRepoRoot config --file .gitmodules --get "submodule.$VeiSubmoduleRelPath.url" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Info "Registering as git submodule..."
            git -c core.autocrlf=false -C $VeiRepoRoot submodule add --force $VeiSubmoduleUrl $VeiSubmoduleRelPath 2>&1 | Out-Null
        }

        $ErrorActionPreference = $SavedEAP
        $veiOk = $true
        foreach ($p in $VeiSparsePaths) { if (-not (Test-Path (Join-Path $VeiAbs $p))) { $veiOk = $false } }
        if ($veiOk) {
            Write-Success "voice-enabled-interactions submodule ready (sparse) at: $VeiAbs"
        }
        else {
            Write-Error-Custom "VEI submodule checkout is missing expected paths."
            exit 1
        }
    }
    else {
        $ErrorActionPreference = $SavedEAP
        Write-Error-Custom "Failed to clone the voice-enabled-interactions submodule."
        Write-Info "Try manually: git clone --depth 1 --filter=blob:none --sparse `"$VeiSubmoduleUrl`" `"$VeiAbs`""
        exit 1
    }
}

# =============================================================================
# STEP 1: Check Python Installation
# =============================================================================

Write-Step "Checking Python 3.11+ installation..."

try {
    $PythonVersion = python --version 2>$null
    if ($PythonVersion -match "3\.(11|12|13)") {
        Write-Success "Python found: $PythonVersion"
    }
    else {
        Write-Error-Custom "Python 3.11+ not found. Current version: $PythonVersion"
        Write-Info "Please install Python 3.11+ from https://www.python.org/downloads/"
        exit 1
    }
}
catch {
    Write-Error-Custom "Python not found in PATH"
    Write-Info "Please install Python 3.11+ from https://www.python.org/downloads/"
    Write-Info "Make sure to check 'Add Python to PATH' during installation"
    exit 1
}

# =============================================================================
# STEP 2: Check/Install FFmpeg
# =============================================================================

Write-Step "Checking FFmpeg installation..."

$FFmpegExists = $false
try {
    $FFmpegVersion = ffmpeg -version 2>$null | Select-Object -First 1
    if ($FFmpegVersion) {
        Write-Success "FFmpeg found: $FFmpegVersion"
        $FFmpegExists = $true
    }
}
catch {}

if (-not $FFmpegExists) {
    Write-Info "FFmpeg not found. Attempting to install..."
    
    # Try winget (preferred)
    try {
        Write-Info "Installing FFmpeg via Windows Package Manager..."
        winget install ffmpeg -e -h --accept-source-agreements 2>$null | Out-Null
        Start-Sleep -Seconds 2
        
        $FFmpegVersion = ffmpeg -version 2>$null | Select-Object -First 1
        if ($FFmpegVersion) {
            Write-Success "FFmpeg installed successfully: $FFmpegVersion"
        }
        else {
            throw "Installation verification failed"
        }
    }
    catch {
        # Try Chocolatey
        try {
            Write-Info "Trying Chocolatey package manager..."
            $ChocoExists = choco --version 2>$null
            if ($ChocoExists) {
                choco install ffmpeg -y 2>$null | Out-Null
                Start-Sleep -Seconds 2
                
                $FFmpegVersion = ffmpeg -version 2>$null | Select-Object -First 1
                if ($FFmpegVersion) {
                    Write-Success "FFmpeg installed via Chocolatey: $FFmpegVersion"
                }
                else {
                    throw "Installation verification failed"
                }
            }
            else {
                throw "Chocolatey not found"
            }
        }
        catch {
            Write-Error-Custom "Could not auto-install FFmpeg"
            Write-Info "Please install manually:"
            Write-Info "  Option 1: winget install ffmpeg"
            Write-Info "  Option 2: choco install ffmpeg"
            Write-Info "  Option 3: Download from https://ffmpeg.org/download.html"
            exit 1
        }
    }
}

# =============================================================================
# STEP 3: Create Virtual Environments
# =============================================================================

Write-Step "Setting up Python virtual environments..."

$Services = @(
    @{ Name = "text-to-speech"; Path = "$EdgeAIDir\microservices\text-to-speech" },
    @{ Name = "audio-analyzer"; Path = "$EdgeAIDir\microservices\audio-analyzer" },
    # rag-service comes from the VEI submodule; its requirements.txt includes the
    # agentic stack (litellm/google-adk) which ATA does not use and which fails to
    # build on Windows. Use the ATA-curated requirements subset instead.
    @{ Name = "rag-service"; Path = "$KioskDir\rag-service"; ReqOverride = "$ScriptDir\configs\rag-service.requirements.windows.txt" },
    @{ Name = "kiosk-core"; Path = "$KioskDir" }
)

function Ensure-WindowsVenv {
    param(
        [hashtable]$Service
    )

    $VenvPath = Join-Path $Service.Path "venv"
    $PythonExe = Join-Path $VenvPath "Scripts\python.exe"

    if (Test-Path $PythonExe) {
        # A python.exe alone is not enough - a venv created without pip (or a
        # partially-created one) will fail later. Verify pip and bootstrap it via
        # ensurepip if missing; only recreate the venv as a last resort.
        & $PythonExe -m pip --version *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Info "Virtual environment ready for $($Service.Name)"
            return
        }

        Write-Info "venv for $($Service.Name) is missing pip; bootstrapping with ensurepip..."
        & $PythonExe -m ensurepip --default-pip *> $null
        & $PythonExe -m pip --version *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "pip bootstrapped for $($Service.Name)"
            return
        }

        Write-Info "ensurepip failed for $($Service.Name); recreating the virtual environment..."
        Remove-Item -Recurse -Force $VenvPath
    }
    elseif (Test-Path $VenvPath) {
        Write-Info "Existing venv for $($Service.Name) is missing Windows python executable; recreating..."
        Remove-Item -Recurse -Force $VenvPath
    }

    Write-Step "Creating virtual environment for $($Service.Name)..."
    Push-Location $Service.Path
    try {
        python -m venv venv
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $PythonExe)) {
            throw "venv creation failed"
        }
        # Make sure pip exists inside the freshly created venv.
        & $PythonExe -m pip --version *> $null
        if ($LASTEXITCODE -ne 0) {
            & $PythonExe -m ensurepip --default-pip *> $null
        }
        & $PythonExe -m pip --version *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "venv created but pip is unavailable"
        }
        Write-Success "Virtual environment created for $($Service.Name)"
    }
    finally {
        Pop-Location
    }
}

function Invoke-NativeInstallCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [Parameter(Mandatory = $true)]
        [scriptblock]$ScriptBlock,
        [switch]$Quiet
    )

    # Under Windows PowerShell with ErrorActionPreference=Stop, native stderr can
    # surface as terminating RemoteException. Run installs with Continue and use
    # the process exit code as the source of truth.
    $SavedEAP = $ErrorActionPreference
    $SavedPSNative = $null
    $ErrorActionPreference = 'Continue'
    if ($Script:HasPSNativeCommandUseErrorActionPreference) {
        $SavedPSNative = $Global:PSNativeCommandUseErrorActionPreference
        $Global:PSNativeCommandUseErrorActionPreference = $false
    }
    try {
        if ($Quiet) {
            & $ScriptBlock *> $null
        }
        else {
            & $ScriptBlock
        }
    }
    finally {
        $ErrorActionPreference = $SavedEAP
        if ($Script:HasPSNativeCommandUseErrorActionPreference) {
            $Global:PSNativeCommandUseErrorActionPreference = $SavedPSNative
        }
    }

    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE"
    }
}

function Invoke-OpenWakeWordOnnxSync {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe
    )

    $SyncPy = @"
import pathlib
import sys
import time

try:
    import requests
    import openwakeword
except Exception as exc:
    print(f"OWW_SYNC_IMPORT_FAILED: {exc}")
    sys.exit(1)

target = pathlib.Path(openwakeword.__file__).resolve().parent / "resources" / "models"
target.mkdir(parents=True, exist_ok=True)

urls = []
for group in (openwakeword.FEATURE_MODELS, openwakeword.MODELS, openwakeword.VAD_MODELS):
    for item in group.values():
        url = item.get("download_url")
        if not url:
            continue
        if url.endswith(".tflite"):
            urls.append(url.replace(".tflite", ".onnx"))
        elif url.endswith(".onnx"):
            urls.append(url)

seen = set()
required = []
for url in urls:
    if url in seen:
        continue
    seen.add(url)
    required.append((url.rsplit("/", 1)[-1], url))

missing = [name for name, _ in required if not (target / name).exists()]
if not missing:
    print(f"OWW_ONNX_SYNC_OK: all {len(required)} ONNX assets already present")
    sys.exit(0)

print(f"OWW_ONNX_SYNC: downloading {len(missing)} missing ONNX assets")
errors = []
session = requests.Session()

for name, url in required:
    out = target / name
    if out.exists() and out.stat().st_size > 0:
        continue

    success = False
    for attempt in range(1, 4):
        try:
            with session.get(url, stream=True, timeout=180) as resp:
                resp.raise_for_status()
                tmp = out.with_suffix(out.suffix + ".tmp")
                with open(tmp, "wb") as handle:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
                tmp.replace(out)
            print(f"OWW_ONNX_SAVED: {name}")
            success = True
            break
        except Exception as exc:
            if attempt == 3:
                errors.append(f"{name} <- {url} :: {exc}")
            else:
                time.sleep(attempt * 2)

    if not success and out.exists() and out.stat().st_size == 0:
        try:
            out.unlink()
        except Exception:
            pass

if errors:
    print("OWW_ONNX_SYNC_FAILED:")
    for err in errors:
        print(err)
    sys.exit(1)

print(f"OWW_ONNX_SYNC_OK: downloaded/verified {len(required)} ONNX assets")
"@

    # Show sync output so failures include direct URL/file diagnostics.
    Invoke-NativeInstallCommand -Command "openwakeword ONNX model sync" -ScriptBlock {
        $SyncPy | & $PythonExe -
    }
}

foreach ($Service in $Services) {
    try {
        Ensure-WindowsVenv -Service $Service
    }
    catch {
        Write-Error-Custom "Failed to prepare venv for $($Service.Name): $_"
        exit 1
    }
}

# =============================================================================
# STEP 4: Install Python Dependencies
# =============================================================================

Write-Step "Installing Python dependencies..."

foreach ($Service in $Services) {
    $VenvPath = Join-Path $Service.Path "venv"
    $PythonExe = Join-Path $VenvPath "Scripts\python.exe"
    $RequirementsFile = Join-Path $Service.Path "requirements.txt"
    # Allow an ATA-specific requirements override (e.g. rag-service, to drop the
    # Windows-incompatible agentic dependencies shipped by the VEI submodule).
    if ($Service.ReqOverride -and (Test-Path $Service.ReqOverride)) {
        $RequirementsFile = $Service.ReqOverride
        Write-Info "Using ATA requirements override for $($Service.Name): $($Service.ReqOverride)"
    }

    if (-not (Test-Path $PythonExe)) {
        Write-Info "Python executable not found for $($Service.Name); recreating virtual environment..."
        try {
            Ensure-WindowsVenv -Service $Service
        }
        catch {
            Write-Error-Custom "Failed to repair venv for $($Service.Name): $_"
            exit 1
        }
    }
    
    if (-not (Test-Path $RequirementsFile)) {
        Write-Info "No requirements.txt found for $($Service.Name), skipping..."
        continue
    }
    
    Write-Step "Installing dependencies for $($Service.Name)..."
    try {
        # Guard against a venv that lost pip (e.g. created without ensurepip).
        & $PythonExe -m pip --version *> $null
        if ($LASTEXITCODE -ne 0) {
            & $PythonExe -m ensurepip --default-pip *> $null
        }
        Invoke-NativeInstallCommand -Command "pip install --upgrade pip setuptools wheel" -Quiet -ScriptBlock {
            & $PythonExe -m pip install --upgrade pip setuptools wheel
        }
        Invoke-NativeInstallCommand -Command "pip install -r $RequirementsFile" -ScriptBlock {
            & $PythonExe -m pip install -r $RequirementsFile
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Dependencies installed for $($Service.Name)"

            # openwakeword pip package ships only .tflite files; download the
            # .onnx models (melspectrogram, embedding_model, etc.) explicitly.
            if ($Service.Name -eq "kiosk-core") {
                Write-Info "Downloading openwakeword ONNX model assets..."
                try {
                    Invoke-OpenWakeWordOnnxSync -PythonExe $PythonExe
                    Write-Success "openwakeword ONNX assets ready"
                }
                catch {
                    # Wake-word is optional by default. Keep setup usable even if
                    # model download fails due to transient network/cert/proxy issues.
                    Write-Warning "openwakeword ONNX model sync failed: $_"
                    Write-Warning "Continuing setup. Wake-word detection will not work until models are available."
                }
            }
        }
        else {
            throw "pip install failed with exit code $LASTEXITCODE"
        }
    }
    catch {
        Write-Error-Custom "Failed to install dependencies for $($Service.Name): $_"
        exit 1
    }
}

# =============================================================================
# STEP 4.5: Build React UI
# =============================================================================

Write-Step "Building React web UI..."

$ReactDir = Join-Path $ScriptDir "assistant-react-ui"
if (Test-Path (Join-Path $ReactDir "package.json")) {
    $NodeOk = $false
    try {
        $NodeVersion = node --version 2>$null
        if ($NodeVersion) { $NodeOk = $true }
    }
    catch {}

    if (-not $NodeOk) {
        Write-Info "Node.js not found. Attempting to install via winget..."
        try {
            winget install OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements --silent | Out-Null
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            $NodeVersion = node --version 2>$null
            if ($NodeVersion) { $NodeOk = $true }
        }
        catch {}
    }

    if (-not $NodeOk) {
        Write-Error-Custom "Node.js is required to build the React UI. Install Node.js LTS and re-run setup."
        exit 1
    }

    Write-Success "Node.js found: $NodeVersion"
    Push-Location $ReactDir
    try {
        Write-Step "Installing UI dependencies (npm install)..."
        npm install --no-fund --no-audit
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
        # Ensure esbuild's native binary is present even if install scripts were skipped.
        if (Test-Path "node_modules/esbuild/install.js") { node "node_modules/esbuild/install.js" | Out-Null }
        Write-Step "Building UI bundle (npm run build)..."
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
        Write-Success "React UI built to assistant-react-ui/dist"
    }
    catch {
        Write-Error-Custom "Failed to build React UI: $_"
        exit 1
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Info "assistant-react-ui not found, skipping UI build"
}

# =============================================================================
# STEP 5: Create Directories for Data/Logs/Cache
# =============================================================================

Write-Step "Creating necessary directories..."

$DirsToCreate = @(
    "$KioskDir\generated_audio",
    "$KioskDir\logs",
    "$EdgeAIDir\microservices\audio-analyzer\storage",
    "$EdgeAIDir\microservices\audio-analyzer\models",
    "$EdgeAIDir\microservices\audio-analyzer\chunks",
    "$EdgeAIDir\microservices\audio-analyzer\.cache",
    "$EdgeAIDir\microservices\text-to-speech\storage",
    "$EdgeAIDir\microservices\text-to-speech\models",
    "$EdgeAIDir\microservices\text-to-speech\.cache",
    "$KioskDir\rag-service\storage",
    "$KioskDir\rag-service\models",
    "$KioskDir\rag-service\.cache",
    "$ScriptDir\.logs"
)

foreach ($Dir in $DirsToCreate) {
    if (-not (Test-Path $Dir)) {
        try {
            New-Item -ItemType Directory -Path $Dir -Force | Out-Null
            Write-Info "Created: $Dir"
        }
        catch {
            Write-Error-Custom "Failed to create directory: $Dir"
        }
    }
}

# =============================================================================
# STEP 6: Create .env file if missing
# =============================================================================

Write-Step "Setting up environment configuration..."

$EnvFile = Join-Path $ScriptDir ".env"
if (-not (Test-Path $EnvFile)) {
    $EnvContent = @"
# Smart Kiosk Assistant - Windows 11 Configuration
# Generated by setup_windows.ps1

# Service URLs (localhost for Windows native)
KIOSK_CORE_ANALYZER_URL=http://127.0.0.1:8010/v1/audio/transcriptions
KIOSK_CORE_RAG_URL=http://127.0.0.1:8020/api/v1/query
KIOSK_CORE_TTS_URL=http://127.0.0.1:8011/v1/audio/speech
KIOSK_CORE_METRICS_URL=http://127.0.0.1:9000

# Gradio UI Configuration
KIOSK_CORE_UI_BASE_URL=http://127.0.0.1:8012
KIOSK_CORE_UI_ANALYZER_URL=http://127.0.0.1:8010/v1/audio/transcriptions
KIOSK_CORE_UI_RAG_URL=http://127.0.0.1:8020/api/v1/query
KIOSK_CORE_UI_TTS_URL=http://127.0.0.1:8011/v1/audio/speech

# Audio Analyzer Configuration
AUDIO_ANALYZER_MICROPHONE=Microphone

# TTS Configuration
TEXT_TO_SPEECH_CORS_ALLOW_ORIGINS=http://127.0.0.1,http://localhost
KIOSK_CORE_TTS_MODEL=qwen-tts
KIOSK_CORE_TTS_VOICE=Ryan
KIOSK_CORE_TTS_LANGUAGE=English

# Performance Settings
KIOSK_CORE_SAMPLE_RATE=16000
KIOSK_CORE_CHUNK_SECONDS=5.0

# ── AI Teaching Assistant feature flags ──────────────────────────────────────
# The kiosk-core + rag-service come from the voice-enabled-interactions submodule
# which ships extra features (agent/ordering, identity, queue, diarization, OVMS).
# ATA runs a lean, local-only Windows configuration, so disable them here.
SMART_KIOSK_RAG__MODELS__LLM__BACKEND=openvino
KIOSK_CORE_ORDERING_ENABLED=false
KIOSK_CORE_IDENTITY_ENABLED=false
KIOSK_CORE_QUEUE_SERVICE_ENABLED=false
KIOSK_CORE_DIARIZATION_ENABLED=false
"@
    try {
        Set-Content -Path $EnvFile -Value $EnvContent
        Write-Success "Created .env configuration file"
    }
    catch {
        Write-Error-Custom "Failed to create .env file: $_"
    }
}
else {
    Write-Info ".env file already exists"
}

# =============================================================================
# STEP 6.5: Pre-build / warm up AI models
#
# Each model-backed service downloads its source model and exports it to
# OpenVINO IR on first startup (inside the FastAPI lifespan, BEFORE the
# /health endpoint becomes available). On a fresh machine this first-run
# export can take many minutes and exceeds the health-check window used by
# start_ata.ps1, making services look like they "never come up".
#
# We do that heavy one-time work here, during setup, where there is no
# health-check timeout. After this completes, start_ata.ps1 finds the
# exported models already on disk and every service becomes healthy quickly.
# =============================================================================

Write-Step "Pre-building AI models (one-time; this can take several minutes)..."

$ModelServices = @(
    @{ Name = "rag-service"; Path = "$KioskDir\rag-service" },
    @{ Name = "text-to-speech"; Path = "$EdgeAIDir\microservices\text-to-speech" },
    @{ Name = "audio-analyzer"; Path = "$EdgeAIDir\microservices\audio-analyzer" }
)

# Python snippet that reproduces exactly what each service does at startup:
# ensure the model is downloaded/exported, then load it into memory once.
$WarmupPy = @"
import sys
try:
    from utils.ensure_model import ensure_model
    from utils.preload_models import preload_models
    ensure_model()
    preload_models()
    print('WARMUP_OK')
except Exception as exc:
    print('WARMUP_FAILED: ' + repr(exc))
    sys.exit(1)
"@

foreach ($Service in $ModelServices) {
    $VenvPath = Join-Path $Service.Path "venv"
    $PythonExe = Join-Path $VenvPath "Scripts\python.exe"

    if (-not (Test-Path $PythonExe)) {
        Write-Error-Custom "Skipping model warmup for $($Service.Name): missing $PythonExe"
        continue
    }

    Write-Step "Warming up models for $($Service.Name) (downloads + OpenVINO export on first run)..."
    Push-Location $Service.Path
    try {
        $WarmupPy | & $PythonExe -
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Models ready for $($Service.Name)"
        }
        else {
            Write-Error-Custom "Model warmup failed for $($Service.Name) (exit code $LASTEXITCODE)"
            Write-Info "The service will retry the export on first startup, which may be slow."
        }
    }
    catch {
        Write-Error-Custom "Model warmup errored for $($Service.Name): $_"
        Write-Info "The service will retry the export on first startup, which may be slow."
    }
    finally {
        Pop-Location
    }
}

# =============================================================================
# STEP 7: Verify Installation
# =============================================================================

Write-Header "VERIFYING INSTALLATION"

Write-Step "Checking Python packages..."

foreach ($Service in $Services) {
    $VenvPath = Join-Path $Service.Path "venv"
    $PythonExe = Join-Path $VenvPath "Scripts\python.exe"
    $RequirementsFile = Join-Path $Service.Path "requirements.txt"

    if (-not (Test-Path $PythonExe)) {
        Write-Error-Custom "Verification skipped for $($Service.Name): missing $PythonExe"
        continue
    }
    
    if (-not (Test-Path $RequirementsFile)) {
        continue
    }
    
    try {
        $Output = & $PythonExe -m pip show pydantic 2>&1
        if ($Output) {
            Write-Success "$($Service.Name) dependencies verified"
        }
        else {
            throw "Package check failed"
        }
    }
    catch {
        Write-Error-Custom "Failed to verify $($Service.Name) dependencies"
    }
}

# =============================================================================
# COMPLETION
# =============================================================================

Write-Header "SETUP COMPLETE"
Write-Success "All components installed successfully!"
Write-Info "Next step: Run start_ata.ps1 to start all services"
Write-Info ""
Write-Info "Usage:"
Write-Info "  powershell -ExecutionPolicy Bypass -File start_ata.ps1"
Write-Info ""
