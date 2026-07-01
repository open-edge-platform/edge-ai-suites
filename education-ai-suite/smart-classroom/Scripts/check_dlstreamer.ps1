<#
.SYNOPSIS
    Checks whether DL Streamer (Deep Learning Streamer) is installed and usable
    by reading its installer registry key, configuring the session environment,
    and running a gst-inspect-1.0 sanity check, and can optionally drive the
    full install / version-upgrade flow.

.DESCRIPTION
    Two modes:

    1. Detection mode (default, optionally with -Quiet):
       Detects DL Streamer via the registry (HKLM:\SOFTWARE\Intel\dlstreamer),
       configures the session by running <InstallDir>\scripts\setup_dls_env.ps1,
       then runs a gst-inspect-1.0 sanity check and reports the result through
       the exit code. When found, the registry version (e.g. "2026.1.0") is
       written to stdout so callers can capture it.

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
      0 -> DL Streamer found via registry and the gvadetect sanity check passed
           (version emitted to stdout)
      1 -> DL Streamer not installed, or gst-inspect-1.0 unavailable after setup
      2 -> DL Streamer installed but the gvadetect sanity check failed

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

# Detect DL Streamer via the registry key written by its installer
# (HKLM:\SOFTWARE\Intel\dlstreamer -> Version, InstallDir), configure the
# session by running <InstallDir>\scripts\setup_dls_env.ps1, then run a
# gst-inspect-1.0 sanity check on the gvadetect element. Returns a
# PSCustomObject with Status ('Found' | 'NotInstalled' | 'NoGstInspect' |
# 'NoPlugin'), plus Version / VersionLine / Source / Package / Plugin /
# InstallDir when available.
function Test-DLStreamer {
    # The installer records the version and install location under this key.
    $reg = Get-ItemProperty -Path 'HKLM:\SOFTWARE\Intel\dlstreamer' -ErrorAction SilentlyContinue
    if (-not $reg -or -not $reg.InstallDir) {
        return [pscustomobject]@{ Status = 'NotInstalled'; Version = $null; VersionLine = $null; Source = $null; Package = $null; Plugin = $null; InstallDir = $null }
    }

    $installDir = $reg.InstallDir
    $version = $reg.Version

    # Configure the DL Streamer environment for this session (sets DLSTREAMER_DIR,
    # GST_PLUGIN_PATH and PATH, and regenerates the GStreamer plugin cache).
    # Invoked with '&' so the script's own 'exit' cannot terminate this process,
    # while its $env: changes still persist because they apply to the process.
    $setupScript = Join-Path $installDir 'scripts\setup_dls_env.ps1'
    if (Test-Path $setupScript) {
        if ($Quiet) { & $setupScript *> $null } else { & $setupScript 1> $null }
    }

    # Sanity check: confirm gst-inspect-1.0 can load the gvadetect element.
    $gstInspect = Get-Command gst-inspect-1.0 -ErrorAction SilentlyContinue
    if (-not $gstInspect) {
        return [pscustomobject]@{ Status = 'NoGstInspect'; Version = $version; VersionLine = $null; Source = $null; Package = $null; Plugin = $null; InstallDir = $installDir }
    }

    $info = gst-inspect-1.0 gvadetect 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $info) {
        return [pscustomobject]@{ Status = 'NoPlugin'; Version = $version; VersionLine = $null; Source = $null; Package = $null; Plugin = $null; InstallDir = $installDir }
    }

    $source = ($info | Select-String "^  Source module" | Select-Object -First 1).Line
    $package = ($info | Select-String "^  Binary package" | Select-Object -First 1).Line
    $versionLine = ($info | Select-String "^  Version" | Select-Object -First 1).Line

    return [pscustomobject]@{ Status = 'Found'; Version = $version; VersionLine = $versionLine; Source = $source; Package = $package; Plugin = 'gvadetect'; InstallDir = $installDir }
}

# Download helper with proxy support (used by -Install mode only). Uses
# System.Net.WebClient, which handles large files through proxies more reliably
# than Invoke-WebRequest; throws on failure so the caller can fall back to curl.
function Invoke-WebRequestWithProxy {
    param(
        [string]$Uri,
        [string]$OutFile
    )

    # Ensure TLS 1.2 is enabled
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

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
    $webClient.DownloadFile($Uri, $OutFile)
}

# Downloads and runs the DL Streamer Windows installer. Returns $true on success.
function Install-DLStreamer {
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host "  DL Streamer Installation" -ForegroundColor Cyan
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

        $downloadSuccess = $false

        try {
            Invoke-WebRequestWithProxy -Uri $downloadUrl -OutFile $installerPath
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

                Start-Process -FilePath "curl.exe" -ArgumentList $curlArgs -Wait -NoNewWindow

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

        Write-Host "    Running DL Streamer installer in silent mode..." -ForegroundColor Gray
        try {
            $process = Start-Process -FilePath $installerPath -ArgumentList "/S" -Wait -PassThru

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
        'NotInstalled' {
            Write-Status "DL Streamer is not installed (registry key HKLM:\SOFTWARE\Intel\dlstreamer not found)." "Yellow"
            exit 1
        }
        'NoGstInspect' {
            Write-Status "gst-inspect-1.0 not available after DL Streamer environment setup." "Yellow"
            exit 1
        }
        'NoPlugin' {
            Write-Status "DL Streamer is installed but the gvadetect sanity check failed." "Yellow"
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
        Write-Host "  [OK] DL Streamer detected (version $dlStreamerVersion)" -ForegroundColor Green
    } else {
        Write-Host "  [OK] DL Streamer detected" -ForegroundColor Green
    }

    # Enforce minimum version: reinstall if the detected version is older than required
    $detectedDlsVersion = $null
    if ($dlStreamerVersion -and [version]::TryParse($dlStreamerVersion, [ref]$detectedDlsVersion)) {
        if ($detectedDlsVersion -lt [version]$RequiredVersion) {
            Write-Host "  [WARN] DL Streamer $dlStreamerVersion is older than the required $RequiredVersion" -ForegroundColor Yellow
            Write-Host ""
            $upgradeChoice = Read-Host "  Reinstall DL Streamer $RequiredVersion now? (Y/N)"
            if ($upgradeChoice -match "^[Yy]") {
                if (Install-DLStreamer) {
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
    Write-Host "  [INFO] DL Streamer is registered but the gvadetect sanity check failed" -ForegroundColor Yellow
}

if (-not $dlStreamerFound) {
    Write-Host "  [INFO] DL Streamer is not installed" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  DL Streamer is required for video analytics pipelines." -ForegroundColor Gray
    Write-Host "  Latest verified version: $RequiredVersion" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  This will download and run the DL Streamer $RequiredVersion installer." -ForegroundColor Gray
    Write-Host ""
    $installChoice = Read-Host "  Install DL Streamer $RequiredVersion now? (Y/N)"

    if ($installChoice -match "^[Yy]") {
        if (Install-DLStreamer) {
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