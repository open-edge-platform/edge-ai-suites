# ==============================================================================
# setup_genicam_runtime.ps1
#
# Sets up the full binary dependencies for the gstgencamsrc GStreamer plugin:
#
#   1. Downloads gstgencamsrc.dll from the "Edge AI Libraries" GitHub release
#      (gstgencamsrc-plugin.zip) and places it in bin\
#
#   2. Downloads the EMVA GenICam Package 2018.06 and extracts the Win64 VC120
#      runtime DLLs into bin\Win64_x64\
#
# Neither DLL is committed to the repository; this script must be run once
# before using GenICam camera input.
#
# Usage
#   .\src\setup_genicam_runtime.ps1
#   .\src\setup_genicam_runtime.ps1 -ReleaseTag "v2026.1.0-rc2"
#   .\src\setup_genicam_runtime.ps1 -BinDir "D:\my\bin" -TempDir "D:\tmp"
#
# Parameters
#   -ReleaseTag  GitHub release tag for edge-ai-libraries containing
#                gstgencamsrc-plugin.zip with gstgencamsrc.dll.
#                Default: v2026.1.0-rc2
#   -BinDir   Destination folder for gstgencamsrc.dll.
#             Default: <repo-root>\bin  (relative to this script's location)
#   -OutDir   Destination folder for the GenICam VC120 runtime DLLs.
#             Default: <BinDir>\Win64_x64
#   -TempDir  Short-path temp dir for zip extraction (avoids Windows MAX_PATH issues).
#             Default: C:\tmp
# ==============================================================================

param(
    [string]$ReleaseTag = "v2026.1.0-rc2",
    [string]$BinDir  = "$PSScriptRoot\..\bin",
    [string]$OutDir  = "",
    [string]$TempDir = "C:\tmp"
)

# Derive OutDir from BinDir if not explicitly supplied
if (-Not $OutDir) { $OutDir = "$BinDir\Win64_x64" }

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression.FileSystem

$DLSTREAMER_ZIP_URL   = "https://github.com/open-edge-platform/edge-ai-libraries/releases/download/$ReleaseTag/gstgencamsrc-plugin.zip"
$DLSTREAMER_ZIP       = "$env:TEMP\gstgencamsrc-plugin.zip"
$GENICAM_DOWNLOAD_URL = "https://www.emva.org/wp-content/uploads/GenICam_Package_2018.06.zip"
$GENICAM_ZIP          = "$env:TEMP\GenICam_Package_2018.06.zip"

# Resolve and create directories
$BinDir = [System.IO.Path]::GetFullPath($BinDir)
$OutDir = [System.IO.Path]::GetFullPath($OutDir)
if (-Not (Test-Path $BinDir)) { New-Item -ItemType Directory -Path $BinDir -Force | Out-Null }
if (-Not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

Write-Host ""
Write-Host "========== Win Vision AI Binary Setup =========="
Write-Host "Release : $ReleaseTag"
Write-Host "BinDir  : $BinDir"
Write-Host "OutDir  : $OutDir"
Write-Host ""

# ============================================================================
# Step 1 — Download gstgencamsrc.dll from the Edge AI Libraries GitHub release
# ============================================================================
Write-Host "[1/2] Downloading gstgencamsrc.dll from release '$ReleaseTag'..."
Write-Host "      URL: $DLSTREAMER_ZIP_URL"
try {
    Invoke-WebRequest -Uri $DLSTREAMER_ZIP_URL -OutFile $DLSTREAMER_ZIP -UseBasicParsing
} catch {
    Write-Error "Failed to download gstgencamsrc-plugin.zip: $_"
    exit 1
}

try {
    $DLSTREAMER_EXTRACT_DIR = "$TempDir\_dls_$PID"
    if (-Not (Test-Path $TempDir)) { New-Item -ItemType Directory -Path $TempDir | Out-Null }
    if (Test-Path $DLSTREAMER_EXTRACT_DIR) { Remove-Item -Recurse -Force $DLSTREAMER_EXTRACT_DIR }
    Expand-Archive -Path $DLSTREAMER_ZIP -DestinationPath $DLSTREAMER_EXTRACT_DIR -Force

    $gstDll = Get-ChildItem $DLSTREAMER_EXTRACT_DIR -Filter "gstgencamsrc.dll" -Recurse | Select-Object -First 1
    if (-Not $gstDll) {
        Write-Host "Contents of extracted zip:"
        Get-ChildItem $DLSTREAMER_EXTRACT_DIR -Recurse | ForEach-Object { Write-Host "  $($_.FullName)" }
        throw "gstgencamsrc.dll not found in gstgencamsrc-plugin.zip."
    }
    Copy-Item -Path $gstDll.FullName -Destination "$BinDir\gstgencamsrc.dll" -Force
    Write-Host "      -> $BinDir\gstgencamsrc.dll"
} finally {
    if (Test-Path $DLSTREAMER_EXTRACT_DIR) { Remove-Item -Recurse -Force $DLSTREAMER_EXTRACT_DIR -ErrorAction SilentlyContinue }
    if (Test-Path $DLSTREAMER_ZIP)          { Remove-Item -Force $DLSTREAMER_ZIP -ErrorAction SilentlyContinue }
}

# ============================================================================
# Step 2 — Download EMVA GenICam Package 2018.06 and extract VC120 runtime DLLs
# ============================================================================
Write-Host ""
Write-Host "[2/2] Downloading GenICam Package 2018.06..."
Write-Host "      URL: $GENICAM_DOWNLOAD_URL"
Invoke-WebRequest -Uri $GENICAM_DOWNLOAD_URL -OutFile $GENICAM_ZIP -UseBasicParsing
Write-Host "      Download complete."

# ============================================================================
# Extract to short temp path (avoids MAX_PATH issues)
# ============================================================================
if (-Not (Test-Path $TempDir)) { New-Item -ItemType Directory -Path $TempDir | Out-Null }
$GENICAM_EXTRACT_DIR = "$TempDir\_gc_$PID"

try {
    Write-Host "Extracting..."
    if (Test-Path $GENICAM_EXTRACT_DIR) { Remove-Item -Recurse -Force $GENICAM_EXTRACT_DIR }
    Expand-Archive -Path $GENICAM_ZIP -DestinationPath $GENICAM_EXTRACT_DIR -Force

    # The GenICam_Package_2018.06.zip is a package-of-packages.
    # The actual Win64 VC120 runtime DLLs live in inner zip files under
    # "Reference Implementation":
    #   *Win64_x64_VS120*Runtime*          -> bin\ (Runtime DLLs)
    #   *Win64_x64_VS120*CommonRuntime*    -> bin\ (shared DLLs)
    #   *Win64_x64_VS120*Development*      -> skipped (headers + import libs not needed)
    $refDir = Get-ChildItem $GENICAM_EXTRACT_DIR -Recurse -Directory -Filter "Reference Implementation" |
        Select-Object -First 1 -ExpandProperty FullName

    if (-Not $refDir) {
        Write-Host "Extracted top-level contents:"
        Get-ChildItem $GENICAM_EXTRACT_DIR -Recurse -Depth 2 | ForEach-Object { Write-Host "  $($_.FullName)" }
        throw "Cannot locate 'Reference Implementation' folder inside the GenICam zip. Unexpected layout."
    }

    $win64Zips = Get-ChildItem $refDir -Filter "*Win64_x64_VS120*.zip"
    if (-Not $win64Zips) {
        throw "No Win64_x64_VS120 zip files found in '$refDir'."
    }

    $copied = 0
    foreach ($z in $win64Zips) {
        if ($z.Name -match "Development") {
            Write-Host "Skipping (headers not needed): $($z.Name)"
            continue
        }

        Write-Host "Extracting: $($z.Name)"
        $zDir = "$GENICAM_EXTRACT_DIR\_$($z.BaseName)"
        Expand-Archive -Path $z.FullName -DestinationPath $zDir -Force

        $srcBin = Get-ChildItem $zDir -Recurse -Directory -Filter "bin" | Select-Object -First 1
        if ($srcBin) {
            # Runtime zips place DLLs in bin\Win64_x64\; unwrap one level so
            # DLLs land directly in $OutDir rather than $OutDir\Win64_x64\.
            $srcWin64 = Get-ChildItem $srcBin.FullName -Directory -Filter "Win64_x64" -ErrorAction SilentlyContinue | Select-Object -First 1
            $copyFrom = if ($srcWin64) { $srcWin64.FullName } else { $srcBin.FullName }
            Write-Host "  Copying Runtime\bin from $($z.BaseName)..."
            $null = robocopy $copyFrom $OutDir /E /256 /NFL /NDL /NJH /NJS
            if ($LASTEXITCODE -gt 7) {
                throw "robocopy failed copying Runtime\bin from $($z.Name) (exit $LASTEXITCODE)"
            }
            $copied++
        } else {
            Write-Warning "No bin\ folder found inside $($z.Name) - skipping."
        }
    }

    if ($copied -eq 0) {
        throw "No runtime DLLs were copied. Unexpected zip structure."
    }

    $dllCount = (Get-ChildItem $OutDir -Filter "*.dll" -ErrorAction SilentlyContinue).Count
    Write-Host ""
    Write-Host "========== Setup Complete =========="
    Write-Host "gstgencamsrc.dll : $BinDir\gstgencamsrc.dll"
    Write-Host "GenICam runtime  : $OutDir ($dllCount file(s))"
    Write-Host ""
    Write-Host "Next steps - set these environment variables before running gst-inspect-1.0 gencamsrc:"
    Write-Host "  `$genicamRuntime = `"$OutDir`""
    Write-Host "  `$env:PATH = `"`$BinDir;`$genicamRuntime;`$env:PATH`""

} catch {
    Write-Error "GenICam runtime setup failed: $_"
    exit 1
} finally {
    if (Test-Path $GENICAM_EXTRACT_DIR) { Remove-Item -Recurse -Force $GENICAM_EXTRACT_DIR -ErrorAction SilentlyContinue }
    if (Test-Path $GENICAM_ZIP) { Remove-Item -Force $GENICAM_ZIP -ErrorAction SilentlyContinue }
}
