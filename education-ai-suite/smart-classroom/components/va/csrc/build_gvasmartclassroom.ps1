# ==============================================================================
# Build script for gvasmartclassroom
# Requires build_dlstreamer_dlls.ps1 to be executed first
# ==============================================================================

$ErrorActionPreference = "Stop"
$SRC_DIR = $PSScriptRoot

# ============================================================================
# Locate VS BuildTools
# ============================================================================
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-Not (Test-Path $vswhere)) {
    Write-Error "vswhere not found. Please run build_dlstreamer_dlls.ps1 first."
    exit 1
}
$vsPath = & $vswhere -latest -products * -property installationPath
if (-Not $vsPath) {
    Write-Error "Visual Studio installation not found."
    exit 1
}
Write-Host "VS installation: $vsPath"

# ============================================================================
# Locate GStreamer
# ============================================================================
$regPath = "HKLM:\SOFTWARE\GStreamer1.0\x86_64"
$regInstallDir = (Get-ItemProperty -Path $regPath -Name "InstallDir" -ErrorAction SilentlyContinue).InstallDir
if ($regInstallDir) {
    $GSTREAMER_ROOT = $regInstallDir.TrimEnd('\')
    if (-Not $GSTREAMER_ROOT.EndsWith('\1.0\msvc_x86_64')) {
        $GSTREAMER_ROOT = "$GSTREAMER_ROOT\1.0\msvc_x86_64"
    }
} else {
    $GSTREAMER_ROOT = "$env:ProgramFiles\gstreamer\1.0\msvc_x86_64"
}
if (-Not (Test-Path $GSTREAMER_ROOT)) {
    Write-Error "GStreamer not found at $GSTREAMER_ROOT. Please run build_dlstreamer_dlls.ps1 first."
    exit 1
}
Write-Host "GStreamer root: $GSTREAMER_ROOT"

# ============================================================================
# Setup environment
# ============================================================================
# PKG_CONFIG_PATH for GStreamer
$env:PKG_CONFIG_PATH = "$GSTREAMER_ROOT\lib\pkgconfig"
Write-Host "PKG_CONFIG_PATH: $env:PKG_CONFIG_PATH"

# VS Developer Shell
$VSDEVSHELL = Join-Path $vsPath "Common7\Tools\Launch-VsDevShell.ps1"
if (Test-Path $VSDEVSHELL) {
    Write-Host "Launching VS Dev Shell..."
    & $VSDEVSHELL -Arch amd64
} else {
    Write-Error "VS Dev Shell script not found at $VSDEVSHELL"
    exit 1
}

# ============================================================================
# CMake configure and build
# ============================================================================
$BUILD_DIR = "$SRC_DIR\build"
If (Test-Path $BUILD_DIR) {
    Write-Host "Cleaning existing build directory..."
    Remove-Item -Recurse -Force $BUILD_DIR
}
New-Item -ItemType Directory -Path $BUILD_DIR | Out-Null
Write-Host "Build directory: $BUILD_DIR"

$VCPKG_CMAKE = Join-Path $vsPath "VC\vcpkg\scripts\buildsystems\vcpkg.cmake"
if (-Not (Test-Path $VCPKG_CMAKE)) {
    Write-Error "vcpkg toolchain not found at $VCPKG_CMAKE"
    exit 1
}
Write-Host "vcpkg toolchain: $VCPKG_CMAKE"

Write-Host ""
Write-Host "========== CMake Configure =========="
cmake -DCMAKE_TOOLCHAIN_FILE="$VCPKG_CMAKE" -S "$SRC_DIR" -B "$BUILD_DIR"
if ($LASTEXITCODE -ne 0) {
    Write-Error "CMake configure failed with exit code: $LASTEXITCODE"
    exit $LASTEXITCODE
}
Write-Host ""
Write-Host "========== CMake Build =========="
cmake --build $BUILD_DIR --parallel $env:NUMBER_OF_PROCESSORS --config Release
if ($LASTEXITCODE -ne 0) {
    Write-Error "CMake build failed with exit code: $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "========== Build Complete =========="
Write-Host "Output: $BUILD_DIR\bin\Release\"
