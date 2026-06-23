<#
.SYNOPSIS
    Checks whether DL Streamer (Deep Learning Streamer) is installed and usable
    by inspecting the available GStreamer plugins via gst-inspect-1.0, and can
    optionally drive the full install / version-upgrade flow.

.DESCRIPTION
    Two modes:

    1. Detection mode (default, optionally with -Quiet):
       Detects DL Streamer plugins via gst-inspect-1.0 and reports the result
       through the exit code. When found, the detected version number (e.g.
       "2026.1.0") is written to stdout so callers can capture it.

    2. Install mode (-Install):
       Runs the complete DL Streamer check used by setup-smart-classroom.ps1:
       detection, minimum-version enforcement (reinstall prompt when the
       installed version is older than -RequiredVersion), post-reinstall
       re-verification, and a fresh-install prompt when nothing is detected.
       The download/installer logic is fully self-contained here. Proxy
       settings can be supplied via -HttpProxy / -HttpsProxy.

.PARAMETER Quiet
    Detection mode only. Suppresses informational console output. The exit code
    still reflects the detection result.

.PARAMETER Install
    Runs the full interactive check + version-gate + install/reinstall flow.

.PARAMETER RequiredVersion
    The minimum DL Streamer version required (default "2026.1.0"). Used by
    -Install mode for the version gate and the installer download.

.PARAMETER HttpProxy
    HTTP proxy URL used for installer downloads in -Install mode.

.PARAMETER HttpsProxy
    HTTPS proxy URL used for installer downloads in -Install mode.

.OUTPUTS
    Detection mode exit codes:
      0 -> DL Streamer plugin found (version emitted to stdout)
      1 -> gst-inspect-1.0 not available (GStreamer/DLStreamer missing)
      2 -> gst-inspect-1.0 present but no DL Streamer plugin found

    Install mode exit codes:
      0 -> DL Streamer present and meets the required version (or freshly
           installed / user kept an acceptable existing version)
      1 -> DL Streamer present but a required reinstall failed
      2 -> DL Streamer not installed (install skipped or failed)

    Example:
      $version = & .\Scripts\check_dlstreamer.ps1 -Quiet
      & .\Scripts\check_dlstreamer.ps1 -Install -HttpProxy $proxy
#>
[CmdletBinding()]
param(
    [switch]$Quiet,
    [switch]$Install,
    [string]$RequiredVersion = "2026.1.0",
    [string]$HttpProxy = "",
    [string]$HttpsProxy = ""
)

# Expose proxy settings to the download helper via script scope
$script:httpProxy = $HttpProxy
$script:httpsProxy = $HttpsProxy

function Write-Status {
    param([string]$Message, [string]$Color = "Gray")
    if (-not $Quiet) {
        Write-Host $Message -ForegroundColor $Color
    }
}

# Inspect available GStreamer plugins and report DL Streamer presence/version.
# Returns a PSCustomObject with Status ('Found' | 'NoGstInspect' | 'NoPlugin'),
# plus Version / VersionLine / Source / Package / Plugin when found.
function Test-DLStreamer {
    $gstInspect = Get-Command gst-inspect-1.0 -ErrorAction SilentlyContinue
    if (-not $gstInspect) {
        return [pscustomobject]@{ Status = 'NoGstInspect'; Version = $null; VersionLine = $null; Source = $null; Package = $null; Plugin = $null }
    }

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

            $versionLine = ($info | Select-String "^  Version").Line
            $versionNumber = $null
            if ($versionLine -and ($versionLine -match "(\d+\.\d+(?:\.\d+)?)")) {
                $versionNumber = $Matches[1]
            }

            return [pscustomobject]@{ Status = 'Found'; Version = $versionNumber; VersionLine = $versionLine; Source = $source; Package = $package; Plugin = $plugin }
        }
    }

    return [pscustomobject]@{ Status = 'NoPlugin'; Version = $null; VersionLine = $null; Source = $null; Package = $null; Plugin = $null }
}

# Download helper with proxy support (used by -Install mode only).
function Invoke-WebRequestWithProxy {
    param(
        [string]$Uri,
        [string]$OutFile,
        [switch]$UseBasicParsing
    )

    # Ensure TLS 1.2 is enabled
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    # For large files (GitHub releases), use WebClient which handles better through proxies
    if ($OutFile -and ($Uri -match "github.com.*releases")) {
        Write-Host "    Using WebClient for large file download..." -ForegroundColor DarkGray
        $webClient = New-Object System.Net.WebClient

        if ($script:httpProxy -or $script:httpsProxy) {
            $proxyUrl = if ($Uri -match "^https") { $script:httpsProxy } else { $script:httpProxy }
            if ($proxyUrl) {
                $proxy = New-Object System.Net.WebProxy($proxyUrl)
                $proxy.UseDefaultCredentials = $true
                $webClient.Proxy = $proxy
            }
        }

        $webClient.Headers.Add("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PowerShell")

        try {
            $webClient.DownloadFile($Uri, $OutFile)
            return
        } catch {
            Write-Host "    WebClient failed, trying Invoke-WebRequest..." -ForegroundColor DarkYellow
        }
    }

    $params = @{
        Uri = $Uri
        UseBasicParsing = $UseBasicParsing
        TimeoutSec = 300
    }

    if ($OutFile) {
        $params.OutFile = $OutFile
    }

    if ($script:httpProxy -or $script:httpsProxy) {
        $proxyUrl = if ($Uri -match "^https") { $script:httpsProxy } else { $script:httpProxy }
        if ($proxyUrl) {
            $params.Proxy = $proxyUrl
            $params.ProxyUseDefaultCredentials = $true
        }
    }

    Invoke-WebRequest @params
}

# Downloads and runs the DL Streamer Windows installer. Returns $true on success.
function Install-DLStreamerDLLs {
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host "  DL Streamer Installer Installation" -ForegroundColor Cyan
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  This method downloads and runs the DL Streamer" -ForegroundColor Gray
    Write-Host "  installer for Windows 64-bit." -ForegroundColor Gray
    Write-Host ""

    $dlsVersion = $RequiredVersion
    $installerName = "dlstreamer-$dlsVersion-win64.exe"
    $downloadUrl = "https://github.com/open-edge-platform/dlstreamer/releases/download/v$dlsVersion/$installerName"
    try {
        Write-Host "  Step 1: Download Installer" -ForegroundColor Yellow
        $installerPath = Join-Path $env:TEMP $installerName

        Write-Host "    Downloading from GitHub releases..." -ForegroundColor Gray
        Write-Host "    URL: $downloadUrl" -ForegroundColor DarkGray
        if ($script:httpProxy) { Write-Host "    Using proxy: $($script:httpProxy)" -ForegroundColor DarkGray }
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

        $downloadSuccess = $false

        try {
            Invoke-WebRequestWithProxy -Uri $downloadUrl -OutFile $installerPath -UseBasicParsing
            if (Test-Path $installerPath) {
                $fileSize = (Get-Item $installerPath).Length
                if ($fileSize -gt 5MB) {
                    $downloadSuccess = $true
                    Write-Host "    [OK] Downloaded: $installerName ($([math]::Round($fileSize/1MB, 1)) MB)" -ForegroundColor Green
                } else {
                    Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
                    Write-Host "    [WARN] Download incomplete, trying alternative method..." -ForegroundColor Yellow
                }
            }
        } catch {
            Write-Host "    [WARN] PowerShell download failed: $($_.Exception.Message)" -ForegroundColor Yellow
        }

        if (-not $downloadSuccess -and (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
            Write-Host "    Trying curl.exe..." -ForegroundColor Gray
            try {
                $curlArgs = @("-L", "-o", "`"$installerPath`"", "--connect-timeout", "60", "--max-time", "600")
                if ($script:httpProxy) {
                    $curlArgs += @("-x", $script:httpProxy)
                }
                $curlArgs += $downloadUrl

                $curlProcess = Start-Process -FilePath "curl.exe" -ArgumentList $curlArgs -Wait -PassThru -NoNewWindow

                if ((Test-Path $installerPath) -and ((Get-Item $installerPath).Length -gt 5MB)) {
                    $downloadSuccess = $true
                    $fileSize = (Get-Item $installerPath).Length
                    Write-Host "    [OK] Downloaded with curl: $installerName ($([math]::Round($fileSize/1MB, 1)) MB)" -ForegroundColor Green
                }
            } catch {
                Write-Host "    [WARN] curl download failed: $_" -ForegroundColor Yellow
            }
        }

        if (-not $downloadSuccess) {
            Write-Host "    [FAIL] Download failed. Please download manually:" -ForegroundColor Red
            Write-Host "    $downloadUrl" -ForegroundColor Cyan
            return $false
        }

        Write-Host ""

        Write-Host "  Step 2: Run Installer" -ForegroundColor Yellow
        Write-Host "    In the installer wizard, set the install path to: C:\dlls_windows" -ForegroundColor Yellow

        Write-Host "    Starting DL Streamer installer..." -ForegroundColor Gray
        try {
            $process = Start-Process -FilePath $installerPath -Wait -PassThru

            if ($process.ExitCode -eq 0) {
                Write-Host "    [OK] Installer completed successfully" -ForegroundColor Green
            } else {
                Write-Host "    [FAIL] Installer exited with code: $($process.ExitCode)" -ForegroundColor Red
                Write-Host "           The DL Streamer installation did not complete successfully." -ForegroundColor DarkYellow
                Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
                return $false
            }
        } catch {
            Write-Host "    [FAIL] Failed to run installer: $_" -ForegroundColor Red
            Write-Host "    Please run the installer manually: $installerPath" -ForegroundColor Yellow
            return $false
        }

        Remove-Item $installerPath -Force -ErrorAction SilentlyContinue

        Write-Host ""
        Write-Host "  ============================================" -ForegroundColor Green
        Write-Host "  DL Streamer Installation Complete!" -ForegroundColor Green
        Write-Host "  ============================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "  The installer has been executed successfully." -ForegroundColor Gray
        Write-Host "  DL Streamer $dlsVersion should now be installed." -ForegroundColor Gray
        Write-Host ""
        Write-Host "  Note: You may need to restart PowerShell or your system" -ForegroundColor Yellow
        Write-Host "        for environment variables to take effect." -ForegroundColor Yellow
        Write-Host ""

        return $true

    } catch {
        Write-Host "    [FAIL] DL Streamer installation error: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "  Manual Installation:" -ForegroundColor Yellow
        Write-Host "    1. Download: $downloadUrl" -ForegroundColor Cyan
        Write-Host "    2. Run the installer exe file" -ForegroundColor Gray
        Write-Host "    3. Follow the on-screen instructions" -ForegroundColor Gray
        Write-Host ""
        return $false
    }
}

# ----------------------------------------------------------------------------
# Detection mode (default): report via exit code, emit version to stdout.
# ----------------------------------------------------------------------------
if (-not $Install) {
    $result = Test-DLStreamer
    switch ($result.Status) {
        'NoGstInspect' {
            Write-Status "Neither GStreamer nor DL Streamer is installed (gst-inspect-1.0 not found)." "Yellow"
            exit 1
        }
        'NoPlugin' {
            Write-Status "DL Streamer plugins not found." "Yellow"
            exit 2
        }
        'Found' {
            Write-Status "DL Streamer plugin found: $($result.Plugin)" "Green"
            Write-Status $result.VersionLine
            Write-Status $result.Source
            Write-Status $result.Package
            # Emit just the version number to the pipeline so callers can capture it
            if ($result.Version) { Write-Output $result.Version }
            exit 0
        }
    }
}

# ----------------------------------------------------------------------------
# Install mode (-Install): full check + version-gate + install/reinstall flow.
# ----------------------------------------------------------------------------
$dlStreamerFound = $false
$appChecksFailed = $false

$result = Test-DLStreamer
if ($result.Status -eq 'Found') {
    $dlStreamerVersion = $result.Version
    $dlStreamerFound = $true
    if ($dlStreamerVersion) {
        Write-Host "  [OK] DL Streamer plugins detected via gst-inspect-1.0 (version $dlStreamerVersion)" -ForegroundColor Green
    } else {
        Write-Host "  [OK] DL Streamer plugins detected via gst-inspect-1.0" -ForegroundColor Green
    }

    # Enforce minimum version: reinstall if the detected version is older than required
    $detectedDlsVersion = $null
    if ($dlStreamerVersion -and [version]::TryParse($dlStreamerVersion, [ref]$detectedDlsVersion)) {
        if ($detectedDlsVersion -lt [version]$RequiredVersion) {
            Write-Host "  [WARN] DL Streamer $dlStreamerVersion is older than the required $RequiredVersion" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "  During installation, set the install path to: C:\dlls_windows" -ForegroundColor Yellow
            $upgradeChoice = Read-Host "  Reinstall DL Streamer $RequiredVersion now? (Y/N)"
            if ($upgradeChoice -match "^[Yy]") {
                if (Install-DLStreamerDLLs) {
                    Write-Host "  [OK] DL Streamer $RequiredVersion installed." -ForegroundColor Green

                    # Post-reinstall: verify the version again
                    Write-Host "  Verifying DL Streamer version after reinstall..." -ForegroundColor White
                    $recheck = Test-DLStreamer
                    $recheckedParsed = $null
                    if ($recheck.Status -eq 'Found' -and $recheck.Version -and [version]::TryParse($recheck.Version, [ref]$recheckedParsed)) {
                        if ($recheckedParsed -ge [version]$RequiredVersion) {
                            Write-Host "  [OK] DL Streamer $($recheck.Version) verified (meets required $RequiredVersion)" -ForegroundColor Green
                        } else {
                            Write-Host "  [WARN] DL Streamer still reports $($recheck.Version) (older than required $RequiredVersion)" -ForegroundColor Yellow
                            Write-Host "         Restart PowerShell and re-run setup to verify the upgrade." -ForegroundColor DarkYellow
                        }
                    } else {
                        Write-Host "  [INFO] Could not verify DL Streamer version in this session." -ForegroundColor Yellow
                        Write-Host "         Restart PowerShell for the updated environment to take effect, then re-run setup." -ForegroundColor Yellow
                    }
                } else {
                    Write-Host "  [FAIL] DL Streamer reinstall failed" -ForegroundColor Red
                    Write-Host "         Please download and run the installer manually from:" -ForegroundColor Cyan
                    Write-Host "         https://github.com/open-edge-platform/dlstreamer/releases/download/v$RequiredVersion/dlstreamer-$RequiredVersion-win64.exe" -ForegroundColor Cyan
                    $appChecksFailed = $true
                }
            } else {
                Write-Host "  [SKIP] Keeping existing DL Streamer $dlStreamerVersion" -ForegroundColor Yellow
                Write-Host "         Video pipelines verified against $RequiredVersion may not work correctly." -ForegroundColor DarkYellow
            }
        }
    }
} elseif ($result.Status -eq 'NoPlugin') {
    Write-Host "  [INFO] DL Streamer plugins not detected via gst-inspect-1.0" -ForegroundColor Yellow
}

if (-not $dlStreamerFound) {
    Write-Host "  [INFO] DL Streamer is not installed" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  DL Streamer is required for video analytics pipelines." -ForegroundColor Gray
    Write-Host "  Latest verified version: $RequiredVersion" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  This will download and run the DL Streamer $RequiredVersion installer." -ForegroundColor Gray
    Write-Host "  During installation, set the install path to: C:\dlls_windows" -ForegroundColor Yellow
    Write-Host ""
    $installChoice = Read-Host "  Install DL Streamer $RequiredVersion now? (Y/N)"

    if ($installChoice -match "^[Yy]") {
        if (Install-DLStreamerDLLs) {
            $dlStreamerFound = $true
        } else {
            Write-Host "  [FAIL] DL Streamer installation failed" -ForegroundColor Red
            Write-Host "         Please download and run the installer manually from:" -ForegroundColor Cyan
            Write-Host "         https://github.com/open-edge-platform/dlstreamer/releases/download/v$RequiredVersion/dlstreamer-$RequiredVersion-win64.exe" -ForegroundColor Cyan
            $appChecksFailed = $true
        }
    } else {
        Write-Host "  [SKIP] DL Streamer installation skipped" -ForegroundColor Yellow
        Write-Host "         Please install manually from: https://github.com/open-edge-platform/dlstreamer/releases" -ForegroundColor Cyan
        $appChecksFailed = $true
    }
}

# Communicate the outcome to the caller via exit code
if (-not $dlStreamerFound) {
    exit 2
} elseif ($appChecksFailed) {
    exit 1
} else {
    exit 0
}