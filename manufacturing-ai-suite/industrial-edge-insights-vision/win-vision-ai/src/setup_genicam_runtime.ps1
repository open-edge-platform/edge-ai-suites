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
#   powershell -ExecutionPolicy Bypass -File src\setup_genicam_runtime.ps1
#   powershell -ExecutionPolicy Bypass -File src\setup_genicam_runtime.ps1 -OutDir "D:\my\folder"
#   powershell -ExecutionPolicy Bypass -File src\setup_genicam_runtime.ps1 -TempDir "D:\tmp"
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

# ── Download ────────────────────────────────────────────────────────────────
Add-Type -AssemblyName System.IO.Compression.FileSystem

Write-Host "Downloading GenICam Package 2018.06..."
Invoke-WebRequest -Uri $GENICAM_DOWNLOAD_URL -OutFile $GENICAM_ZIP -UseBasicParsing
Write-Host "Download complete."

# ── Extract to short temp path (avoids MAX_PATH issues) ─────────────────────
if (-Not (Test-Path $TempDir)) { New-Item -ItemType Directory -Path $TempDir | Out-Null }
$ExtractDir = "$TempDir\_gc_$PID"

try {
    Write-Host "Extracting outer zip..."
    if (Test-Path $ExtractDir) { Remove-Item -Recurse -Force $ExtractDir }
    Expand-Archive -Path $GENICAM_ZIP -DestinationPath $ExtractDir -Force

    # The outer zip contains a top-level folder with a "Reference Implementation" subfolder
    # that holds the per-platform inner zips.
    $refDir = Get-ChildItem $ExtractDir -Recurse -Directory -Filter "Reference Implementation" |
        Select-Object -First 1 -ExpandProperty FullName

    if (-Not $refDir) {
        Write-Host "Extracted top-level contents:"
        Get-ChildItem $ExtractDir -Recurse -Depth 2 | ForEach-Object { Write-Host "  $($_.FullName)" }
        throw "Cannot locate 'Reference Implementation' folder inside the GenICam zip. Unexpected layout."
    }

    # Find all Win64_x64_VS120 zips — skip Development, extract Runtime DLLs only.
    # Relevant zips: Runtime, CommonRuntime, FirmwareUpdateRuntime (all contain a bin\ folder).
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
        $zDir = "$ExtractDir\_$($z.BaseName)"
        Expand-Archive -Path $z.FullName -DestinationPath $zDir -Force

        $srcBin = Get-ChildItem $zDir -Recurse -Directory -Filter "bin" | Select-Object -First 1
        if ($srcBin) {
            Write-Host "  Copying DLLs from $($z.BaseName)..."
            $null = robocopy $srcBin.FullName $OutDir /E /256 /NFL /NDL /NJH /NJS
            if ($LASTEXITCODE -gt 7) {
                throw "robocopy failed copying from $($z.Name) (exit $LASTEXITCODE)"
            }
            $copied++
        } else {
            Write-Warning "No bin\ folder found inside $($z.Name) — skipping."
        }
    }

    if ($copied -eq 0) {
        throw "No runtime DLLs were copied. Unexpected zip structure."
    }

    $dllCount = (Get-ChildItem $OutDir -Filter "*.dll" -ErrorAction SilentlyContinue).Count
    Write-Host ""
    Write-Host "Done. $dllCount DLL(s) in: $OutDir"
    Write-Host ""
    Write-Host "Next steps — set these environment variables before running gst-inspect-1.0 gencamsrc:"
    Write-Host "  `$genicamRuntime = `"$OutDir`""
    Write-Host "  `$env:PATH = `"`$genicamRuntime;`$env:PATH`""

} finally {
    if (Test-Path $ExtractDir) {
        Remove-Item -Recurse -Force $ExtractDir -ErrorAction SilentlyContinue
    }
    if (Test-Path $GENICAM_ZIP) {
        Remove-Item -Force $GENICAM_ZIP -ErrorAction SilentlyContinue
    }
}
