# ==============================================================================
# setup_genicam_runtime.ps1
#
# Downloads the EMVA GenICam Package 2018.06 and extracts the Win64 VC120
# runtime DLLs into the win-vision-ai bin\Win64_x64\ folder.
#
# The extracted DLLs are required at runtime for the gstgencamsrc GStreamer
# plugin (bin\gstgencamsrc.dll) to load on Windows.
#
# Usage
#   .\src\setup_genicam_runtime.ps1
#   .\src\setup_genicam_runtime.ps1 -OutDir "D:\my\folder"
#   .\src\setup_genicam_runtime.ps1 -TempDir "D:\tmp"
#
# Parameters
#   -OutDir   Destination folder for the runtime DLLs.
#             Default: <repo-root>\bin\Win64_x64  (relative to this script's location)
#   -TempDir  Short-path temp dir for zip extraction (avoids Windows MAX_PATH issues).
#             Default: C:\tmp
# ==============================================================================

param(
    [string]$OutDir  = "$PSScriptRoot\..\bin\Win64_x64",
    [string]$TempDir = "C:\tmp"
)

$ErrorActionPreference = "Stop"

$GENICAM_DOWNLOAD_URL = "https://www.emva.org/wp-content/uploads/GenICam_Package_2018.06.zip"
$GENICAM_ZIP          = "$env:TEMP\GenICam_Package_2018.06.zip"

# Resolve and create output directory
$OutDir = [System.IO.Path]::GetFullPath($OutDir)
if (-Not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

Write-Host ""
Write-Host "========== GenICam Runtime DLL Setup =========="
Write-Host "Output : $OutDir"
Write-Host "URL    : $GENICAM_DOWNLOAD_URL"
Write-Host ""

# ============================================================================
# Download
# ============================================================================
Add-Type -AssemblyName System.IO.Compression.FileSystem

Write-Host "Downloading GenICam Package 2018.06..."
Invoke-WebRequest -Uri $GENICAM_DOWNLOAD_URL -OutFile $GENICAM_ZIP -UseBasicParsing
Write-Host "Download complete."

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
    Write-Host "GenICam runtime DLLs extracted to: $OutDir ($dllCount file(s))"
    Write-Host ""
    Write-Host "Next steps - set these environment variables before running gst-inspect-1.0 gencamsrc:"
    Write-Host "  `$genicamRuntime = `"$OutDir`""
    Write-Host "  `$env:PATH = `"`$genicamRuntime;`$env:PATH`""

} catch {
    Write-Error "GenICam runtime setup failed: $_"
    exit 1
} finally {
    if (Test-Path $GENICAM_EXTRACT_DIR) { Remove-Item -Recurse -Force $GENICAM_EXTRACT_DIR -ErrorAction SilentlyContinue }
    if (Test-Path $GENICAM_ZIP) { Remove-Item -Force $GENICAM_ZIP -ErrorAction SilentlyContinue }
}
