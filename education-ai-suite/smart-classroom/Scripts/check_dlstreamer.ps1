<#
.SYNOPSIS
    Checks whether DL Streamer (Deep Learning Streamer) is installed and usable
    by inspecting the available GStreamer plugins via gst-inspect-1.0.

.DESCRIPTION
    Returns exit code 0 when a DL Streamer plugin is detected, and a non-zero
    exit code otherwise. Designed to be called from setup-smart-classroom.ps1
    without hindering the setup flow:
      - It never calls exit on the parent (it is meant to be invoked as a
        separate script, e.g.  & .\Scripts\check_dlstreamer.ps1).
      - Use -Quiet to suppress all console output (only the exit code is set).

.PARAMETER Quiet
    Suppresses informational console output. The exit code still reflects the
    detection result.

.OUTPUTS
    Exit code 0  -> DL Streamer plugin found
    Exit code 1  -> gst-inspect-1.0 not available (GStreamer/DLStreamer missing)
    Exit code 2  -> gst-inspect-1.0 present but no DL Streamer plugin found
#>
[CmdletBinding()]
param(
    [switch]$Quiet
)

function Write-Status {
    param([string]$Message, [string]$Color = "Gray")
    if (-not $Quiet) {
        Write-Host $Message -ForegroundColor $Color
    }
}

# Check if gst-inspect-1.0 exists
$gstInspect = Get-Command gst-inspect-1.0 -ErrorAction SilentlyContinue

if (-not $gstInspect) {
    Write-Status "Neither GStreamer nor DL Streamer is installed (gst-inspect-1.0 not found)." "Yellow"
    exit 1
}

# Get plugin names
$plugins = gst-inspect-1.0 2>$null |
    Select-String "^[A-Za-z0-9_]+:" |
    ForEach-Object {
        ($_ -split ':')[1].Trim()
    }

foreach ($plugin in $plugins) {
    $info = gst-inspect-1.0 $plugin 2>$null

    $source = ($info | Select-String "^  Source module").Line
    $package = ($info | Select-String "^  Binary package").Line

    if ($source -match "dlstreamer" -or
        $package -match "Deep Learning Streamer") {

        $version = ($info | Select-String "^  Version").Line

        Write-Status "DL Streamer plugin found: $plugin" "Green"
        Write-Status $version
        Write-Status $source
        Write-Status $package
        exit 0
    }
}

Write-Status "DL Streamer plugins not found." "Yellow"
exit 2