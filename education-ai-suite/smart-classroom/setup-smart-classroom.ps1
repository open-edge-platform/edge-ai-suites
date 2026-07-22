#!/usr/bin/env pwsh
param(
    [switch]$Help,
    [switch]$NoElevate,
    [switch]$Silent
)

# ============================================================================
# WINDOWS-ONLY CHECK
# ============================================================================
$IsWindowsOS = $IsWindows -or ($PSVersionTable.PSVersion.Major -lt 6) -or ($env:OS -eq "Windows_NT")

if (-not $IsWindowsOS) {
    Write-Host "ERROR: This script is designed for Windows only." -ForegroundColor Red
    exit 1
}

# ============================================================================
# AUTO-ELEVATE TO ADMINISTRATOR
# ============================================================================
if (-not $NoElevate) {
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    
    if (-not $isAdmin) {
        Write-Host "Requesting Administrator privileges..." -ForegroundColor Yellow
        
        $argList = "-NoExit -ExecutionPolicy Bypass -File `"$PSCommandPath`""
        if ($Help) { $argList += " -Help" }
        if ($Silent) { $argList += " -Silent" }
        $argList += " -NoElevate"  # Prevent infinite elevation loop
        
        try {
            Start-Process powershell -Verb RunAs -ArgumentList $argList
            Write-Host "Elevated window launched. You can close this window." -ForegroundColor Green
            exit 0
        } catch {
            Write-Host "Failed to elevate. Please run as Administrator manually." -ForegroundColor Red
            Write-Host "Right-click PowerShell -> Run as Administrator" -ForegroundColor Yellow
            exit 1
        }
    }
}

if ($Help) {
    Write-Host @"
Smart Classroom Setup Script

Usage: ./setup-smart-classroom.ps1 [-Help] [-NoElevate] [-Silent]

Options:
    -Help       Show this help message
    -NoElevate  Skip auto-elevation to Administrator (Windows)
    -Silent     Unattended mode - auto-install dependencies, no prompts

System Requirements:
  - OS: Windows 11
  - Processor: Intel Core Ultra Series 1, 2, or 3 (with iGPU)
  - Memory: 32 GB RAM (minimum)
  - Storage: 50 GB free
  - Python: 3.12.x
  - Node.js: v18+
  - NPU Driver: Intel NPU Driver (for Core Ultra)

Application Dependencies:
  - FFmpeg: Required for audio processing
  - DL Streamer: Required for video pipelines (v2026.1.0 verified)

Proxy Configuration:
  If behind a corporate firewall, the script will prompt for proxy settings.
  Settings are saved to .proxy-config for future runs.
  Common Intel proxy: http://proxy-iind.intel.com:912

This script will:
  1. Configure proxy for downloads (if needed)
  2. Check system requirements (OS, RAM, Python, Node.js, etc.)
  3. Check application dependencies (FFmpeg, DL Streamer)
  4. Configure smart-classroom settings (language, upload limits, OCR, board OCR)
  5. Launch the startup script

"@ -ForegroundColor Cyan
    exit 0
}

# ============================================================================
# HEADER
# ============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   SMART CLASSROOM SETUP SCRIPT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# SCRIPT DIRECTORY DETECTION
# ============================================================================
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $ScriptDir) { $ScriptDir = Get-Location }

Write-Host "Script location: $ScriptDir" -ForegroundColor Gray
Write-Host ""

# ============================================================================
# PROXY CONFIGURATION (for downloads)
# ============================================================================
Write-Host "PROXY CONFIGURATION" -ForegroundColor Green
Write-Host "-------------------" -ForegroundColor Green

$script:httpProxy = ""
$script:httpsProxy = ""
$script:noProxy = ""
$proxyConfigFile = Join-Path $ScriptDir ".proxy-config"

if (Test-Path $proxyConfigFile) {
    $proxyConfig = Get-Content $proxyConfigFile | ConvertFrom-Json
    $script:httpProxy = $proxyConfig.httpProxy
    $script:httpsProxy = $proxyConfig.httpsProxy
    $script:noProxy = $proxyConfig.noProxy

    Write-Host ""
    Write-Host "  Saved proxy settings found:" -ForegroundColor Cyan
    if ($script:httpProxy) { Write-Host "    HTTP_PROXY:  $($script:httpProxy)" -ForegroundColor Gray }
    if ($script:httpsProxy) { Write-Host "    HTTPS_PROXY: $($script:httpsProxy)" -ForegroundColor Gray }
    if ($script:noProxy) { Write-Host "    NO_PROXY:    $($script:noProxy)" -ForegroundColor Gray }
    if (-not $script:httpProxy -and -not $script:httpsProxy) { 
        Write-Host "    (No proxy configured in .proxy-config)" -ForegroundColor Gray 
        
        # Check environment for proxy settings
        Write-Host ""
        Write-Host "  Checking environment for existing proxy settings..." -ForegroundColor Gray
        $envHttpProxy = if ($env:HTTP_PROXY) { $env:HTTP_PROXY } elseif ($env:http_proxy) { $env:http_proxy } else { "" }
        $envHttpsProxy = if ($env:HTTPS_PROXY) { $env:HTTPS_PROXY } elseif ($env:https_proxy) { $env:https_proxy } else { "" }
        $envNoProxy = if ($env:NO_PROXY) { $env:NO_PROXY } elseif ($env:no_proxy) { $env:no_proxy } else { "" }
        
        $envProxies = Get-ChildItem Env:\*proxy* -ErrorAction SilentlyContinue
        if ($envProxies) {
            $envProxies | ForEach-Object {
                Write-Host "    Found: $($_.Name) = $($_.Value)" -ForegroundColor Cyan
            }
            Write-Host ""
            Write-Host "  Environment variables detected. You can save these to .proxy-config." -ForegroundColor Yellow
        } else {
            Write-Host "    (No proxy environment variables found)" -ForegroundColor Gray
        }
    }
    Write-Host ""

    if ($Silent) {
        Write-Host "  Silent mode: using saved proxy settings" -ForegroundColor Gray
        $changeProxy = "N"
    } else {
        if (-not $script:httpProxy -and -not $script:httpsProxy -and ($envHttpProxy -or $envHttpsProxy)) {
            Write-Host "  [Y] Yes - Configure different proxy settings" -ForegroundColor White
            Write-Host "  [N] No  - Save environment proxy settings to .proxy-config" -ForegroundColor White
            Write-Host "  [S] Skip - No proxy (direct connection)" -ForegroundColor White
        } else {
            Write-Host "  [Y] Yes - Change proxy settings" -ForegroundColor White
            Write-Host "  [N] No  - Use saved proxy settings" -ForegroundColor White
            Write-Host "  [S] Skip - No proxy (direct connection)" -ForegroundColor White
        }
        Write-Host ""
        $changeProxy = Read-Host "Do you want to change proxy settings? (Y/N/S)"
    }
    
    if ($changeProxy -match "^[Yy]") {
        Write-Host ""
        Write-Host "Enter new proxy settings (press Enter to keep current value):" -ForegroundColor Yellow
        Write-Host "  (Common Intel proxy: http://proxy-iind.intel.com:912)" -ForegroundColor DarkGray
        Write-Host ""
        
        $newHttpProxy = Read-Host "HTTP_PROXY  [$($script:httpProxy)]"
        $newHttpsProxy = Read-Host "HTTPS_PROXY [$($script:httpsProxy)]"
        $newNoProxy = Read-Host "NO_PROXY    [$($script:noProxy)]"
        
        if ($newHttpProxy) { $script:httpProxy = $newHttpProxy }
        if ($newHttpsProxy) { $script:httpsProxy = $newHttpsProxy }
        if ($newNoProxy) { $script:noProxy = $newNoProxy }
        
        $proxyConfig = @{
            httpProxy = $script:httpProxy
            httpsProxy = $script:httpsProxy
            noProxy = $script:noProxy
        }
        $proxyConfig | ConvertTo-Json | Set-Content $proxyConfigFile
        Write-Host "  Proxy settings updated and saved." -ForegroundColor Green
    } elseif ($changeProxy -match "^[Ss]") {
        $script:httpProxy = ""
        $script:httpsProxy = ""
        Write-Host "  No proxy - using direct connection." -ForegroundColor Yellow
    } else {
        # If .proxy-config is empty but environment has proxy, save environment values
        if (-not $script:httpProxy -and -not $script:httpsProxy -and ($envHttpProxy -or $envHttpsProxy)) {
            $script:httpProxy = $envHttpProxy
            $script:httpsProxy = $envHttpsProxy
            $script:noProxy = $envNoProxy
            
            $proxyConfig = @{
                httpProxy = $script:httpProxy
                httpsProxy = $script:httpsProxy
                noProxy = $script:noProxy
            }
            $proxyConfig | ConvertTo-Json | Set-Content $proxyConfigFile
            Write-Host "  Environment proxy settings saved to .proxy-config:" -ForegroundColor Green
            if ($script:httpProxy) { Write-Host "    HTTP_PROXY:  $($script:httpProxy)" -ForegroundColor Gray }
            if ($script:httpsProxy) { Write-Host "    HTTPS_PROXY: $($script:httpsProxy)" -ForegroundColor Gray }
            if ($script:noProxy) { Write-Host "    NO_PROXY:    $($script:noProxy)" -ForegroundColor Gray }
        } else {
            Write-Host "  Using saved proxy settings." -ForegroundColor Gray
        }
    }
} else {
    Write-Host ""
    Write-Host "  No proxy configuration found in .proxy-config file." -ForegroundColor Gray
    Write-Host "  Checking environment for existing proxy settings..." -ForegroundColor Gray
    Write-Host ""
    
    # Check environment variables for proxy settings
    $envHttpProxy = if ($env:HTTP_PROXY) { $env:HTTP_PROXY } elseif ($env:http_proxy) { $env:http_proxy } else { "" }
    $envHttpsProxy = if ($env:HTTPS_PROXY) { $env:HTTPS_PROXY } elseif ($env:https_proxy) { $env:https_proxy } else { "" }
    $envNoProxy = if ($env:NO_PROXY) { $env:NO_PROXY } elseif ($env:no_proxy) { $env:no_proxy } else { "" }
    
    $envProxies = Get-ChildItem Env:\*proxy* -ErrorAction SilentlyContinue
    if ($envProxies) {
        $envProxies | ForEach-Object {
            Write-Host "    Found: $($_.Name) = $($_.Value)" -ForegroundColor Cyan
        }
        Write-Host ""
        Write-Host "  Environment variables detected. You can save these or configure different settings." -ForegroundColor Yellow
    } else {
        Write-Host "    (No proxy environment variables found)" -ForegroundColor Gray
    }
    Write-Host ""

    if ($Silent) {
        Write-Host "  Silent mode: using environment proxy settings if available" -ForegroundColor Gray
        $configureProxy = "N"
    } else {
        if ($envHttpProxy -or $envHttpsProxy) {
            Write-Host "  [Y] Yes  - Configure different proxy settings" -ForegroundColor White
            Write-Host "  [N] No   - Save current environment proxy settings to .proxy-config" -ForegroundColor White
        } else {
            Write-Host "  [Y] Yes  - Configure proxy (save to .proxy-config)" -ForegroundColor White
            Write-Host "  [N] No   - No proxy (direct connection)" -ForegroundColor White
        }
        Write-Host ""
        $configureProxy = Read-Host "Do you want to configure a proxy? (Y/N)"
    }

    if ($configureProxy -match "^[Yy]") {
        Write-Host ""
        Write-Host "Enter proxy settings:" -ForegroundColor Yellow
        Write-Host "  (Common Intel proxy: http://proxy-iind.intel.com:912)" -ForegroundColor DarkGray
        Write-Host ""
        
        $script:httpProxy = Read-Host "HTTP_PROXY"
        $script:httpsProxy = Read-Host "HTTPS_PROXY (press Enter to use same as HTTP)"
        $script:noProxy = Read-Host "NO_PROXY"
        
        if (-not $script:httpsProxy -and $script:httpProxy) {
            $script:httpsProxy = $script:httpProxy
        }
        
        $proxyConfig = @{
            httpProxy = $script:httpProxy
            httpsProxy = $script:httpsProxy
            noProxy = $script:noProxy
        }
        $proxyConfig | ConvertTo-Json | Set-Content $proxyConfigFile
        Write-Host "  Proxy settings saved to .proxy-config" -ForegroundColor Green
    } else {
        # If environment variables exist, save them; otherwise save empty config
        if ($envHttpProxy -or $envHttpsProxy) {
            $script:httpProxy = $envHttpProxy
            $script:httpsProxy = $envHttpsProxy
            $script:noProxy = $envNoProxy
            
            $proxyConfig = @{
                httpProxy = $script:httpProxy
                httpsProxy = $script:httpsProxy
                noProxy = $script:noProxy
            }
            $proxyConfig | ConvertTo-Json | Set-Content $proxyConfigFile
            Write-Host "  Environment proxy settings saved to .proxy-config:" -ForegroundColor Green
            if ($script:httpProxy) { Write-Host "    HTTP_PROXY:  $($script:httpProxy)" -ForegroundColor Gray }
            if ($script:httpsProxy) { Write-Host "    HTTPS_PROXY: $($script:httpsProxy)" -ForegroundColor Gray }
            if ($script:noProxy) { Write-Host "    NO_PROXY:    $($script:noProxy)" -ForegroundColor Gray }
        } else {
            $proxyConfig = @{
                httpProxy = ""
                httpsProxy = ""
                noProxy = ""
            }
            $proxyConfig | ConvertTo-Json | Set-Content $proxyConfigFile
            Write-Host "  No proxy configured. Settings saved." -ForegroundColor Gray
        }
    }
}

# Function to download with proxy support
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
        
        # Add progress indicator
        $webClient.Headers.Add("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PowerShell")
        
        try {
            $webClient.DownloadFile($Uri, $OutFile)
            return
        } catch {
            Write-Host "    WebClient failed, trying Invoke-WebRequest..." -ForegroundColor DarkYellow
        }
    }
    
    # Standard method for smaller files or API calls
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

Write-Host ""

# ============================================================================
# [1] CHECK SYSTEM REQUIREMENTS
# ============================================================================
Write-Host "[1] CHECK SYSTEM REQUIREMENTS" -ForegroundColor Green
Write-Host "------------------------------" -ForegroundColor Green
Write-Host ""

$systemRequirementsDocPath = Join-Path $PSScriptRoot "docs\user-guide\get-started\system-requirements.md"
$systemRequirementsDocUrl = "https://github.com/open-edge-platform/edge-ai-suites/blob/main/education-ai-suite/smart-classroom/docs/user-guide/get-started/system-requirements.md#software-and-hardware-requirements"

function Show-SystemRequirementsFromDoc {
    param(
        [string]$DocPath,
        [string]$DocUrl,
        [string]$SectionHeader = "Software and Hardware Requirements"
    )

    Write-Host "System Requirements:" -ForegroundColor Yellow

    if (-not (Test-Path $DocPath)) {
        return
    }

    $docLines = Get-Content -Path $DocPath -Encoding UTF8
    $sectionStart = -1
    for ($i = 0; $i -lt $docLines.Count; $i++) {
        if ($docLines[$i] -match "^##\s+$([regex]::Escape($SectionHeader))\s*$") {
            $sectionStart = $i
            break
        }
    }

    if ($sectionStart -eq -1) {
        return
    }

    $sectionEnd = $docLines.Count
    for ($j = $sectionStart + 1; $j -lt $docLines.Count; $j++) {
        if ($docLines[$j] -match "^##\s+") {
            $sectionEnd = $j
            break
        }
    }

    $sectionLines = $docLines[($sectionStart + 1)..($sectionEnd - 1)]
    foreach ($line in $sectionLines) {
        if ($line -match "^\s*-\s+") {
            $displayLine = $line.Trim()
            $displayLine = $displayLine -replace "^-\s+", "  "
            $displayLine = $displayLine -replace "\*\*", ""
            $displayLine = $displayLine -replace "\[([^\]]+)\]\(([^\)]+)\)", '$1 ($2)'
            Write-Host $displayLine -ForegroundColor Gray
        }
    }

    Write-Host ""
}

Show-SystemRequirementsFromDoc -DocPath $systemRequirementsDocPath -DocUrl $systemRequirementsDocUrl
Write-Host "  Source:" -ForegroundColor Yellow
Write-Host "  $systemRequirementsDocUrl" -ForegroundColor Cyan
Write-Host ""
if ($Silent) {
    Write-Host "Silent mode: proceeding with setup automatically..." -ForegroundColor Gray
} else {
    Write-Host "Please review the system requirements above." -ForegroundColor Yellow
    $proceedChecks = Read-Host "Would you like to proceed with the setup? (Y/N)"
    if ($proceedChecks -notmatch "^[Yy]") {
        Write-Host ""
        Write-Host "Setup cancelled by user." -ForegroundColor Yellow
        exit 0
    }
}
Write-Host ""

$checksFailed = $false
$warnings = @()

Write-Host "Checking OS..." -ForegroundColor White
try {
    $osInfo = Get-CimInstance -ClassName Win32_OperatingSystem
    $osCaption = $osInfo.Caption
    $osBuild = [int]$osInfo.BuildNumber
    
    if ($osBuild -ge 22000) {
        Write-Host "  [OK] $osCaption (Build $osBuild)" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] Windows 11 required, found: $osCaption" -ForegroundColor Red
        $checksFailed = $true
    }
} catch {
    Write-Host "  [WARN] Could not detect OS version" -ForegroundColor Yellow
    $warnings += "OS version could not be verified"
}

Write-Host "Checking Processor..." -ForegroundColor White
try {
    $cpuInfo = Get-CimInstance -ClassName Win32_Processor | Select-Object -First 1
    $cpuName = $cpuInfo.Name
    
    if ($cpuName -match "Intel.*Core.*Ultra") {
        Write-Host "  [OK] $cpuName" -ForegroundColor Green
    } elseif ($cpuName -match "Intel") {
        Write-Host "  [WARN] $cpuName" -ForegroundColor Yellow
        Write-Host "         Intel Core Ultra Series recommended for optimal performance" -ForegroundColor DarkYellow
        $warnings += "Intel Core Ultra Series recommended"
    } else {
        Write-Host "  [WARN] $cpuName" -ForegroundColor Yellow
        Write-Host "         Intel Core Ultra Series recommended for optimal performance" -ForegroundColor DarkYellow
        $warnings += "Intel processor recommended"
    }
} catch {
    Write-Host "  [WARN] Could not detect processor" -ForegroundColor Yellow
    $warnings += "Processor could not be verified"
}

Write-Host "Checking Memory..." -ForegroundColor White
try {
    $memInfo = Get-CimInstance -ClassName Win32_ComputerSystem
    $totalMemGB = [math]::Round($memInfo.TotalPhysicalMemory / 1GB, 1)
    
    if ($totalMemGB -ge 30) {
        Write-Host "  [OK] $totalMemGB GB RAM" -ForegroundColor Green
    } elseif ($totalMemGB -ge 16) {
        Write-Host "  [WARN] $totalMemGB GB RAM (32 GB recommended)" -ForegroundColor Yellow
        $warnings += "32 GB RAM recommended, found $totalMemGB GB"
    } else {
        Write-Host "  [FAIL] $totalMemGB GB RAM (32 GB minimum required)" -ForegroundColor Red
        $checksFailed = $true
    }
} catch {
    Write-Host "  [WARN] Could not detect memory" -ForegroundColor Yellow
    $warnings += "Memory could not be verified"
}

Write-Host "Checking Storage..." -ForegroundColor White
try {
    $driveLetter = (Split-Path -Qualifier $ScriptDir)
    $driveInfo = Get-PSDrive -Name $driveLetter.TrimEnd(':') -ErrorAction SilentlyContinue
    
    if ($driveInfo) {
        $freeSpaceGB = [math]::Round($driveInfo.Free / 1GB, 1)
        
        if ($freeSpaceGB -ge 50) {
            Write-Host "  [OK] $freeSpaceGB GB free on $driveLetter" -ForegroundColor Green
        } elseif ($freeSpaceGB -ge 30) {
            Write-Host "  [WARN] $freeSpaceGB GB free on $driveLetter (50 GB recommended)" -ForegroundColor Yellow
            $warnings += "50 GB free space recommended, found $freeSpaceGB GB"
        } else {
            Write-Host "  [FAIL] $freeSpaceGB GB free on $driveLetter (50 GB minimum required)" -ForegroundColor Red
            $checksFailed = $true
        }
    } else {
        Write-Host "  [WARN] Could not check free space on $driveLetter" -ForegroundColor Yellow
        $warnings += "Storage space could not be verified"
    }
} catch {
    Write-Host "  [WARN] Could not detect storage" -ForegroundColor Yellow
    $warnings += "Storage could not be verified"
}

Write-Host "Checking GPU..." -ForegroundColor White
try {
    $gpuList = Get-CimInstance -ClassName Win32_VideoController
    $intelGpuFound = $false
    $gpuNames = @()
    
    foreach ($gpu in $gpuList) {
        $gpuNames += $gpu.Name
        if ($gpu.Name -match "Intel.*(Arc|Core Ultra|Iris|UHD|Graphics)") {
            $intelGpuFound = $true
        }
    }
    
    if ($intelGpuFound) {
        $intelGpuObj = $gpuList | Where-Object { $_.Name -match "Intel.*(Arc|Core Ultra|Iris|UHD|Graphics)" } | Select-Object -First 1
        Write-Host "  [OK] $($intelGpuObj.Name)" -ForegroundColor Green

        # Driver version check
        $installedVersion = $intelGpuObj.DriverVersion
        if ($installedVersion) {
            $majorVersion = [int]($installedVersion.Split('.')[0])

            # Latest known driver for supported GPUs (Arc / Core Ultra use the 32.x branch)
            $latestVersionMap = @{
                32 = "32.0.101.8826"   # Arc / Iris Xe / Core Ultra Series 1, 2, 3
            }

            Write-Host "  Driver version: $installedVersion" -ForegroundColor Gray

            if ($latestVersionMap.ContainsKey($majorVersion)) {
                $latestVersion = $latestVersionMap[$majorVersion]

                if ([version]$installedVersion -ge [version]$latestVersion) {
                    Write-Host "  [OK] Driver is up to date (latest: $latestVersion)" -ForegroundColor Green
                } else {
                    Write-Host "  [WARN] Driver is outdated - latest is $latestVersion" -ForegroundColor Yellow
                    Write-Host "         Please Download and install the latest version (https://www.intel.com/content/www/us/en/search.html)" -ForegroundColor Cyan
                    $warnings += "Intel GPU driver is outdated (installed: $installedVersion, latest: $latestVersion)"
                }
            } else {
                Write-Host "  [INFO] Unknown driver family (v$majorVersion) - verify manually at https://www.intel.com/content/www/us/en/search.html" -ForegroundColor DarkYellow
            }
        }
    } else {
        Write-Host "  [WARN] Supported Intel GPU not detected" -ForegroundColor Yellow
        Write-Host "         Found: $($gpuNames -join ', ')" -ForegroundColor DarkYellow
        Write-Host "         Required: Intel iGPU (Core Ultra Series 1, Arc GPU, or higher) for summarization acceleration" -ForegroundColor DarkYellow
        $warnings += "Intel iGPU (Core Ultra Series 1, Arc GPU, or higher) required for summarization acceleration"
    }
} catch {
    Write-Host "  [WARN] Could not detect GPU" -ForegroundColor Yellow
    $warnings += "GPU could not be verified"
}

function Install-NPUDriver {
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host "  Intel NPU Driver Installation" -ForegroundColor Cyan
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
    
    $npuDriverVersion = "32.0.100.4778"
    $npuDriverFileName = "npu_win_$npuDriverVersion.exe"
    $npuDriverUrl = "https://downloadmirror.intel.com/919954/$npuDriverFileName"
    $npuDriverPath = Join-Path $env:TEMP $npuDriverFileName
    
    Write-Host "  Intel NPU Driver version: $npuDriverVersion" -ForegroundColor Gray
    Write-Host "  Supports: Core Ultra Series 1, 2, 3 (Meteor Lake, Arrow Lake, Lunar Lake, Panther Lake)" -ForegroundColor Gray
    Write-Host ""
    
    Write-Host "  Step 1: Downloading NPU Driver..." -ForegroundColor Yellow
    Write-Host "    URL: $npuDriverUrl" -ForegroundColor DarkGray
    if ($script:httpProxy) { Write-Host "    Using proxy: $($script:httpProxy)" -ForegroundColor DarkGray }
    
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    
    $downloadSuccess = $false
    
    try {
        Invoke-WebRequestWithProxy -Uri $npuDriverUrl -OutFile $npuDriverPath -UseBasicParsing
        if (Test-Path $npuDriverPath) {
            $fileSize = (Get-Item $npuDriverPath).Length
            if ($fileSize -gt 10MB) {
                $downloadSuccess = $true
                Write-Host "    [OK] Downloaded: $npuDriverFileName ($([math]::Round($fileSize/1MB, 1)) MB)" -ForegroundColor Green
            } else {
                Remove-Item $npuDriverPath -Force -ErrorAction SilentlyContinue
                Write-Host "    [WARN] Download incomplete, trying curl..." -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host "    [WARN] PowerShell download failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    
    if (-not $downloadSuccess -and (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
        Write-Host "    Trying curl.exe..." -ForegroundColor Gray
        try {
            $curlArgs = @("-L", "-o", $npuDriverPath, "--connect-timeout", "60", "--max-time", "600")
            if ($script:httpProxy) {
                $curlArgs += @("-x", $script:httpProxy)
            }
            $curlArgs += $npuDriverUrl
            
            & curl.exe @curlArgs 2>&1 | Out-Null
            
            if ((Test-Path $npuDriverPath) -and ((Get-Item $npuDriverPath).Length -gt 10MB)) {
                $downloadSuccess = $true
                $fileSize = (Get-Item $npuDriverPath).Length
                Write-Host "    [OK] Downloaded with curl: $npuDriverFileName ($([math]::Round($fileSize/1MB, 1)) MB)" -ForegroundColor Green
            }
        } catch {
            Write-Host "    [WARN] curl download failed: $_" -ForegroundColor Yellow
        }
    }
    
    if (-not $downloadSuccess) {
        Write-Host "    [FAIL] Download failed." -ForegroundColor Red
        Write-Host ""
        Write-Host "  Manual Download Required:" -ForegroundColor Yellow
        Write-Host "    1. Go to: https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html" -ForegroundColor Cyan
        Write-Host "    2. Download the NPU driver installer" -ForegroundColor Gray
        Write-Host "    3. Run the installer and restart your computer" -ForegroundColor Gray
        Write-Host "    4. Re-run this setup script to verify NPU detection" -ForegroundColor Gray
        Write-Host ""
        return $false
    }
    
    Write-Host ""
    
    Write-Host "  Step 2: Running NPU Driver Installer..." -ForegroundColor Yellow
    Write-Host "    Please follow the on-screen instructions." -ForegroundColor Gray
    Write-Host "    The installer window will open shortly..." -ForegroundColor Gray
    Write-Host ""
    
    try {
        $process = Start-Process -FilePath $npuDriverPath -Wait -PassThru
        
        Remove-Item $npuDriverPath -Force -ErrorAction SilentlyContinue
        
        if ($process.ExitCode -eq 0) {
            Write-Host "    [OK] NPU Driver installation completed" -ForegroundColor Green
        } else {
            Write-Host "    [INFO] Installer exited with code: $($process.ExitCode)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "    [WARN] Could not run installer: $_" -ForegroundColor Yellow
        Write-Host "    Please run the installer manually: $npuDriverPath" -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Yellow
    Write-Host "  IMPORTANT: System Restart Required" -ForegroundColor Yellow
    Write-Host "  ============================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  To complete NPU driver installation:" -ForegroundColor White
    Write-Host "    1. Restart your computer" -ForegroundColor Gray
    Write-Host "    2. Re-run this setup script to verify NPU detection" -ForegroundColor Gray
    Write-Host ""
    
    $npuDevicesRecheck = Get-PnpDevice -ErrorAction SilentlyContinue | 
                        Where-Object { $_.FriendlyName -match "Intel.*(NPU|Neural|AI Boost|VPU|Accelerator)" }
    
    if ($npuDevicesRecheck) {
        $npuName = ($npuDevicesRecheck | Select-Object -First 1).FriendlyName
        Write-Host "  [OK] NPU detected: $npuName" -ForegroundColor Green
        return $true
    } else {
        Write-Host "  [INFO] NPU not yet detected - restart required" -ForegroundColor Yellow
        return $false
    }
}

Write-Host "Checking NPU..." -ForegroundColor White
try {
    # Check multiple device classes where NPU might appear (System, Compute, SoftwareComponent)
    $npuDevices = Get-PnpDevice -ErrorAction SilentlyContinue | 
                  Where-Object { $_.FriendlyName -match "NPU|Neural|AI Boost|VPU" -and $_.FriendlyName -match "Intel" }
    
    if (-not $npuDevices) {
        # Broader search including Accelerator keyword
        $npuDevices = Get-PnpDevice -ErrorAction SilentlyContinue | 
                      Where-Object { $_.FriendlyName -match "Intel.*(NPU|Neural|AI Boost|VPU|Accelerator)" }
    }
    
    if ($npuDevices) {
        $npuDevice = $npuDevices | Select-Object -First 1
        $npuName = $npuDevice.FriendlyName
        $npuStatus = $npuDevice.Status
        
        if ($npuStatus -eq "OK") {
            Write-Host "  [OK] $npuName" -ForegroundColor Green
            
            # Try to get driver version information from registry and WMI
            $npuDriverVersion = $null
            try {
                $instanceId = $npuDevice.InstanceId
                
                # Method 1: Check device registry for DriverVersion
                $regPath = "HKLM:\SYSTEM\CurrentControlSet\Enum\$instanceId"
                if (Test-Path $regPath) {
                    $deviceProps = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
                    
                    # Try to get from Device Parameters
                    $deviceParamsPath = "$regPath\Device Parameters"
                    if (Test-Path $deviceParamsPath) {
                        $deviceParams = Get-ItemProperty -Path $deviceParamsPath -ErrorAction SilentlyContinue
                        if ($deviceParams -and $deviceParams.DriverVersion) {
                            $npuDriverVersion = $deviceParams.DriverVersion
                        }
                    }
                    
                    # Fallback: Check direct properties
                    if (-not $npuDriverVersion -and $deviceProps.DriverVersion) {
                        $npuDriverVersion = $deviceProps.DriverVersion
                    }
                }
                
                # Method 2: Use WMI to find driver by device name
                if (-not $npuDriverVersion) {
                    $signedDrivers = Get-CimInstance -ClassName Win32_PnPSignedDriver -ErrorAction SilentlyContinue | 
                                    Where-Object { $_.DeviceName -match "Intel.*(NPU|Neural|AI Boost|VPU)" }
                    
                    if ($signedDrivers) {
                        $driver = $signedDrivers | Select-Object -First 1
                        if ($driver.DriverVersion) {
                            $npuDriverVersion = $driver.DriverVersion
                        }
                    }
                }
                
                if ($npuDriverVersion) {
                    Write-Host "  Driver version: $npuDriverVersion" -ForegroundColor Gray
                    
                    # Define known latest versions for NPU drivers
                    $latestVersionMap = @{
                        "32" = "32.0.100.4778"   # Core Ultra Series 1, 2, 3 (Meteor Lake, Arrow Lake, Lunar Lake, Panther Lake)
                    }
                    
                    # Parse version and compare
                    $installedMajor = [int]($npuDriverVersion.Split('.')[0])
                    
                    if ($latestVersionMap.ContainsKey($installedMajor.ToString())) {
                        $latestVersion = $latestVersionMap[$installedMajor.ToString()]
                        
                        try {
                            $installedVersion = [version]$npuDriverVersion
                            $latestVersionObj = [version]$latestVersion
                            
                            if ($installedVersion -ge $latestVersionObj) {
                                Write-Host "  [OK] Driver is up to date (latest: $latestVersion)" -ForegroundColor Green
                            } else {
                                Write-Host "  [WARN] NPU driver is outdated - latest is $latestVersion" -ForegroundColor Yellow
                                Write-Host "         Please download and install the latest version" -ForegroundColor Cyan
                                Write-Host "         https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html" -ForegroundColor Cyan
                                $warnings += "Intel NPU driver is outdated (installed: $npuDriverVersion, latest: $latestVersion)"
                            }
                        } catch {
                            Write-Host "  [INFO] Could not parse driver version - manual verification may be needed" -ForegroundColor DarkYellow
                        }
                    } else {
                        Write-Host "  [INFO] Unknown driver family (v$installedMajor) - verify manually at https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html" -ForegroundColor DarkYellow
                    }
                } else {
                    Write-Host "  [INFO] Could not retrieve driver version - verify at https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html" -ForegroundColor DarkYellow
                }
            } catch {
                Write-Host "  [INFO] Could not check driver version details" -ForegroundColor DarkYellow
            }
        } else {
            Write-Host "  [WARN] $npuName (Status: $npuStatus)" -ForegroundColor Yellow
            Write-Host "         NPU driver may need to be updated" -ForegroundColor DarkYellow
            Write-Host ""
            if ($Silent) {
                Write-Host "  [SKIP] Silent mode: skipping NPU driver update" -ForegroundColor Yellow
                $warnings += "NPU detected but status is $npuStatus (skipped in silent mode)"
            } else {
                $updateDriver = Read-Host "  Do you want to update the NPU driver? (Y/N)"
                if ($updateDriver -match "^[Yy]") {
                    Install-NPUDriver | Out-Null
                } else {
                    $warnings += "NPU detected but status is $npuStatus"
                }
            }
        }
    } else {
        Write-Host "  [WARN] Intel NPU not detected" -ForegroundColor Yellow
        Write-Host "         Intel NPU (Core Ultra Series) recommended for Video pipelines" -ForegroundColor DarkYellow
        Write-Host ""
        if ($Silent) {
            Write-Host "  [SKIP] Silent mode: skipping NPU driver installation" -ForegroundColor Yellow
            $warnings += "Intel NPU not detected (skipped in silent mode)"
        } else {
            $installNpu = Read-Host "  Do you want to install the Intel NPU driver? (Y/N)"
            if ($installNpu -match "^[Yy]") {
                if (-not (Install-NPUDriver)) {
                    $warnings += "Intel NPU driver installation pending (restart may be required)"
                }
            } else {
                $warnings += "Intel NPU recommended for Video pipelines"
            }
        }
    }
} catch {
    Write-Host "  [WARN] Could not detect NPU" -ForegroundColor Yellow
    $warnings += "NPU could not be verified"
}

Write-Host "Checking Python version..." -ForegroundColor White

function Install-Python312 {
    $Version = "3.12.10"
    
    Write-Host ""
    Write-Host "  Installing Python $Version..." -ForegroundColor Yellow
    
    $is64Bit = [Environment]::Is64BitOperatingSystem
    if ($is64Bit) {
        $installerName = "python-$Version-amd64.exe"
    } else {
        $installerName = "python-$Version.exe"
    }
    
    $installerUrl = "https://www.python.org/ftp/python/$Version/$installerName"
    $installerPath = Join-Path $env:TEMP $installerName
    
    try {
        Write-Host "  Downloading from: $installerUrl" -ForegroundColor Gray
        if ($script:httpProxy) { Write-Host "  Using proxy: $($script:httpProxy)" -ForegroundColor DarkGray }
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequestWithProxy -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
        
        if (Test-Path $installerPath) {
            Write-Host "  Running installer (this may take a few minutes)..." -ForegroundColor Gray
            
            $arguments = "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0"
            $process = Start-Process -FilePath $installerPath -ArgumentList $arguments -Wait -PassThru
            
            if ($process.ExitCode -eq 0) {
                Write-Host "  [OK] Python $Version installed successfully" -ForegroundColor Green
                
                Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
                
                # Detect Python installation directory
                $pythonExe = $null
                $versionShort = "Python" + ($Version -replace "^(\d+)\.(\d+).*", '$1$2')  # e.g. Python312
                $candidatePaths = @(
                    "C:\Program Files\$versionShort",
                    "C:\Program Files (x86)\$versionShort",
                    "$env:LOCALAPPDATA\Programs\Python\$versionShort"
                )
                foreach ($candidate in $candidatePaths) {
                    if (Test-Path "$candidate\python.exe") {
                        $pythonExe = "$candidate\python.exe"
                        break
                    }
                }
                # Fallback: ask where.exe
                if (-not $pythonExe) {
                    try {
                        $whereResult = (where.exe python 2>$null) | Select-Object -First 1
                        if ($whereResult -and (Test-Path $whereResult)) { $pythonExe = $whereResult }
                    } catch {}
                }
                
                if ($pythonExe) {
                    $pythonDir     = Split-Path -Parent $pythonExe
                    $pythonScripts = Join-Path $pythonDir "Scripts"
                    
                    function Add-PathEntries {
                        param(
                            [string]$Scope,
                            [string[]]$Entries
                        )

                        try {
                            $currentPath = [System.Environment]::GetEnvironmentVariable("Path", $Scope)
                            if (-not $currentPath) { $currentPath = "" }
                            $pathParts = @($currentPath -split ";" | Where-Object { $_ -and $_.Trim() })
                            foreach ($entry in $Entries) {
                                if (-not (Test-Path $entry)) { continue }

                                $exists = $false
                                foreach ($part in $pathParts) {
                                    if ($part.TrimEnd('\\') -ieq $entry.TrimEnd('\\')) {
                                        $exists = $true
                                        break
                                    }
                                }
                                if ($exists) {
                                    Write-Host "  Already in $Scope PATH: $entry" -ForegroundColor DarkGray
                                    continue
                                }
                                $pathParts += $entry
                                Write-Host "  Added to $Scope PATH: $entry" -ForegroundColor Gray
                            }
                            $newPath = ($pathParts -join ";")
                            [System.Environment]::SetEnvironmentVariable("Path", $newPath, $Scope)
                        } catch {
                            Write-Host "  [WARN] Could not update $Scope PATH: $($_.Exception.Message)" -ForegroundColor Yellow
                        }
                    }

                    $entriesToAdd = @($pythonDir, $pythonScripts)
                    Add-PathEntries -Scope "Machine" -Entries $entriesToAdd
                    Add-PathEntries -Scope "User" -Entries $entriesToAdd
                    Write-Host "  [OK] Python PATH entries updated" -ForegroundColor Green
                } else {
                    Write-Host "  [WARN] Could not locate Python install dir - PATH not updated" -ForegroundColor Yellow
                }
                
                # Refresh current session PATH
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
                Write-Host "  NOTE: Restart PowerShell if 'python' is still not recognised" -ForegroundColor Cyan
                
                return $true
            } else {
                Write-Host "  [FAIL] Installer exited with code: $($process.ExitCode)" -ForegroundColor Red
                return $false
            }
        } else {
            Write-Host "  [FAIL] Download failed" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "  [FAIL] Installation error: $_" -ForegroundColor Red
        return $false
    }
}

$pythonInstalled = $false
$pythonNeedsInstall = $false

try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python (\d+)\.(\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        $patch = [int]$Matches[3]
        
        if ($major -eq 3 -and $minor -eq 12) {
            Write-Host "  [OK] Python $major.$minor.$patch" -ForegroundColor Green
            $pythonInstalled = $true
        } else {
            Write-Host "  [WARN] Python 3.12.x required, found $major.$minor.$patch" -ForegroundColor Yellow
            $pythonNeedsInstall = $true
        }
    } else {
        Write-Host "  [INFO] Python not detected" -ForegroundColor Yellow
        $pythonNeedsInstall = $true
    }
} catch {
    Write-Host "  [INFO] Python is not installed" -ForegroundColor Yellow
    $pythonNeedsInstall = $true
}

# Auto-install if not found or wrong version
if ($pythonNeedsInstall) {
    Write-Host ""
    if ($Silent) {
        Write-Host "  Silent mode: auto-installing Python 3.12.10..." -ForegroundColor Yellow
        $installChoice = "Y"
    } else {
        $installChoice = Read-Host "  Install Python 3.12.10 now? (Y/N)"
    }

    if ($installChoice -match "^[Yy]") {
        if (Install-Python312) {
            # Verify installation
            try {
                $newPythonVersion = python --version 2>&1
                if ($newPythonVersion -match "Python 3\.12") {
                    $pythonInstalled = $true
                } else {
                    $defaultPythonCmd = Get-Command python -ErrorAction SilentlyContinue
                    $defaultPythonPath = if ($defaultPythonCmd) { $defaultPythonCmd.Source } else { "unknown" }

                    Write-Host "  [WARN] python --version points to a different default interpreter: $newPythonVersion" -ForegroundColor Yellow
                    Write-Host "  [INFO] Current default python path: $defaultPythonPath" -ForegroundColor DarkYellow
                    Write-Host "  [INFO] Attempting to make Python 3.12 the default by prioritizing PATH entries..." -ForegroundColor Gray

                    $python312Exe = $null
                    $python312Candidates = @(
                        "C:\Program Files\Python312\python.exe",
                        "C:\Program Files (x86)\Python312\python.exe",
                        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
                    )

                    foreach ($candidate in $python312Candidates) {
                        if (Test-Path $candidate) {
                            $python312Exe = $candidate
                            break
                        }
                    }

                    if (-not $python312Exe) {
                        try {
                            $whereResults = where.exe python 2>$null
                            foreach ($wherePath in $whereResults) {
                                if ($wherePath -match "Python312\\python\.exe$" -and (Test-Path $wherePath)) {
                                    $python312Exe = $wherePath
                                    break
                                }
                            }
                        } catch {}
                    }

                    if ($python312Exe) {
                        $python312Dir = Split-Path -Parent $python312Exe
                        $python312Scripts = Join-Path $python312Dir "Scripts"
                        $priorityEntries = @($python312Dir, $python312Scripts)

                        foreach ($scope in @("Machine", "User")) {
                            try {
                                $currentPath = [System.Environment]::GetEnvironmentVariable("Path", $scope)
                                if (-not $currentPath) { $currentPath = "" }

                                $pathParts = @($currentPath -split ";" | Where-Object { $_ -and $_.Trim() })

                                foreach ($entry in $priorityEntries) {
                                    $pathParts = @($pathParts | Where-Object { $_.TrimEnd('\\') -ine $entry.TrimEnd('\\') })
                                }

                                $existingPriorityEntries = @($priorityEntries | Where-Object { Test-Path $_ })
                                $newPath = (@($existingPriorityEntries + $pathParts) -join ";")
                                [System.Environment]::SetEnvironmentVariable("Path", $newPath, $scope)
                                Write-Host "  [OK] Prioritized Python 3.12 in $scope PATH" -ForegroundColor Green
                            } catch {
                                Write-Host "  [WARN] Could not prioritize Python 3.12 in $scope PATH: $($_.Exception.Message)" -ForegroundColor Yellow
                            }
                        }

                        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

                        $recheckedPythonVersion = python --version 2>&1
                        $recheckedPythonCmd = Get-Command python -ErrorAction SilentlyContinue
                        $recheckedPythonPath = if ($recheckedPythonCmd) { $recheckedPythonCmd.Source } else { "unknown" }

                        if ($recheckedPythonVersion -match "Python 3\.12") {
                            Write-Host "  [OK] python now points to Python 3.12 ($recheckedPythonVersion)" -ForegroundColor Green
                            Write-Host "  [INFO] Default python path is now: $recheckedPythonPath" -ForegroundColor DarkGray
                            $pythonInstalled = $true
                        } else {
                            Write-Host "  [WARN] python still resolves to: $recheckedPythonVersion" -ForegroundColor Yellow
                            Write-Host "  [HINT] Default python path remains: $recheckedPythonPath" -ForegroundColor DarkYellow
                            $warnings += "Installed Python 3.12, but python --version still resolves to '$recheckedPythonVersion' at '$recheckedPythonPath'. PATH precedence still points to a different interpreter."
                        }
                    } else {
                        Write-Host "  [WARN] Python 3.12 executable was installed but could not be located for PATH prioritization" -ForegroundColor Yellow
                        $warnings += "Installed Python 3.12, but could not locate Python312 executable to prioritize PATH. python --version currently reports: $newPythonVersion"
                    }
                }
            } catch {
                Write-Host "  [WARN] Python installed but not yet in PATH" -ForegroundColor Yellow
                Write-Host "         Please restart PowerShell and run this script again" -ForegroundColor Cyan
                $pythonInstalled = $true  # Don't fail, just warn
            }
        } else {
            Write-Host "  [FAIL] Python installation failed" -ForegroundColor Red
            Write-Host "         Please install manually from: https://www.python.org/downloads/release/python-31210/" -ForegroundColor Cyan
            $checksFailed = $true
        }
    } else {
        Write-Host "  [SKIP] Python installation skipped" -ForegroundColor Yellow
        Write-Host "         Please install manually from: https://www.python.org/downloads/release/python-31210/" -ForegroundColor Cyan
        $checksFailed = $true
    }
}

Write-Host "Checking Node.js version..." -ForegroundColor White

function Get-LatestNodeLTSVersion {
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        
        # Build proxy parameters
        $params = @{
            Uri = "https://nodejs.org/dist/index.json"
            UseBasicParsing = $true
        }
        if ($script:httpProxy) {
            $params.Proxy = $script:httpProxy
            $params.ProxyUseDefaultCredentials = $true
        }
        $indexJson = Invoke-RestMethod @params
        
        $latestLTS = $indexJson | Where-Object { $_.lts -ne $false } | Select-Object -First 1
        
        if ($latestLTS) {
            return $latestLTS.version.TrimStart('v')
        }
    } catch {
        Write-Host "  [WARN] Could not fetch latest version, using fallback" -ForegroundColor Yellow
    }
    return "22.15.0"
}

function Install-NodeJS {
    Write-Host ""
    Write-Host "  Fetching latest Node.js LTS version..." -ForegroundColor Gray
    
    $Version = Get-LatestNodeLTSVersion
    Write-Host "  Installing Node.js v$Version (Latest LTS)..." -ForegroundColor Yellow
    
    $arch = if ([Environment]::Is64BitOperatingSystem) { "x64" } else { "x86" }
    $msiUrl = "https://nodejs.org/dist/v$Version/node-v$Version-$arch.msi"
    $msiPath = Join-Path $env:TEMP "node-v$Version-$arch.msi"
    
    try {
        Write-Host "  Downloading from: $msiUrl" -ForegroundColor Gray
        if ($script:httpProxy) { Write-Host "  Using proxy: $($script:httpProxy)" -ForegroundColor DarkGray }
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequestWithProxy -Uri $msiUrl -OutFile $msiPath -UseBasicParsing
        
        if (Test-Path $msiPath) {
            Write-Host "  Running installer (this may take a minute)..." -ForegroundColor Gray
            
            $process = Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$msiPath`" /qn /norestart" -Wait -PassThru
            
            if ($process.ExitCode -eq 0) {
                Write-Host "  [OK] Node.js v$Version installed successfully" -ForegroundColor Green
                Write-Host "  NOTE: You may need to restart PowerShell for PATH changes" -ForegroundColor Cyan
                
                Remove-Item $msiPath -Force -ErrorAction SilentlyContinue
                
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
                
                return $true
            } else {
                Write-Host "  [FAIL] Installer exited with code: $($process.ExitCode)" -ForegroundColor Red
                return $false
            }
        } else {
            Write-Host "  [FAIL] Download failed" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "  [FAIL] Installation error: $_" -ForegroundColor Red
        return $false
    }
}

$nodeInstalled = $false
$nodeNeedsUpgrade = $false

try {
    $nodeVersion = node --version 2>&1
    if ($nodeVersion -match "v(\d+)\.(\d+)\.(\d+)") {
        $nodeMajor = [int]$Matches[1]
        $nodeMinor = [int]$Matches[2]
        $nodePatch = [int]$Matches[3]
        
        if ($nodeMajor -ge 18) {
            Write-Host "  [OK] Node.js v$nodeMajor.$nodeMinor.$nodePatch" -ForegroundColor Green
            $nodeInstalled = $true
        } else {
            Write-Host "  [WARN] Node.js v18+ required, found v$nodeMajor.$nodeMinor.$nodePatch" -ForegroundColor Yellow
            $nodeNeedsUpgrade = $true
        }
    } else {
        Write-Host "  [INFO] Node.js not detected" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [INFO] Node.js is not installed" -ForegroundColor Yellow
}

# Auto-install if not found or needs upgrade
if (-not $nodeInstalled) {
    Write-Host ""
    if ($Silent) {
        Write-Host "  Silent mode: auto-installing Node.js v22 LTS..." -ForegroundColor Yellow
        $installChoice = "Y"
    } else {
        $installChoice = Read-Host "  Install Node.js v22 LTS now? (Y/N)"
    }

    if ($installChoice -match "^[Yy]") {
        if (Install-NodeJS) {
            # Verify installation
            try {
                $newNodeVersion = node --version 2>&1
                if ($newNodeVersion -match "v(\d+)") {
                    $nodeInstalled = $true
                }
            } catch {
                Write-Host "  [WARN] Node.js installed but not yet in PATH" -ForegroundColor Yellow
                Write-Host "         Please restart PowerShell and run this script again" -ForegroundColor Cyan
                $nodeInstalled = $true  # Don't fail, just warn
            }
        } else {
            Write-Host "  [FAIL] Node.js installation failed" -ForegroundColor Red
            Write-Host "         Please install manually from: https://nodejs.org/en/download/" -ForegroundColor Cyan
            $checksFailed = $true
        }
    } else {
        Write-Host "  [SKIP] Node.js installation skipped" -ForegroundColor Yellow
        Write-Host "         Please install manually from: https://nodejs.org/en/download/" -ForegroundColor Cyan
        $checksFailed = $true
    }
}

if ($checksFailed) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  SYSTEM REQUIREMENTS NOT MET" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please address the following:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Windows 11:" -ForegroundColor White
    Write-Host "    Required for optimal compatibility" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Memory (32 GB RAM minimum):" -ForegroundColor White
    Write-Host "    Required for model loading and inference" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Storage (50 GB free):" -ForegroundColor White
    Write-Host "    Required for models, logs, and cache" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Python 3.12.x:" -ForegroundColor White
    Write-Host "    https://www.python.org/downloads/release/python-3120/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Node.js v18+ (LTS recommended):" -ForegroundColor White
    Write-Host "    https://nodejs.org/en/download/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Intel NPU Driver (for Core Ultra):" -ForegroundColor White
    Write-Host "    https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

# Show warnings summary if any
if ($warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "Warnings:" -ForegroundColor Yellow
    foreach ($warn in $warnings) {
        Write-Host "  - $warn" -ForegroundColor DarkYellow
    }
    Write-Host ""
    if ($Silent) {
        Write-Host "Silent mode: continuing with $($warnings.Count) warning(s)..." -ForegroundColor Yellow
    } else {
        $continueSetup = Read-Host "Do you still want to continue with the setup? (Y/N)"
        if ($continueSetup -notmatch "^[Yy]") {
            Write-Host ""
            Write-Host "Setup cancelled by user." -ForegroundColor Yellow
            exit 0
        }
    }
}

Write-Host ""
Write-Host "System requirements check passed!" -ForegroundColor Green
Write-Host ""

# ============================================================================
# [2] APPLICATION DEPENDENCY CHECK (Auto-Install)
# ============================================================================
Write-Host "[2] APPLICATION DEPENDENCY CHECK" -ForegroundColor Green
Write-Host "---------------------------------" -ForegroundColor Green
Write-Host ""

$appChecksFailed = $false

function Install-FFmpeg {
    Write-Host ""
    Write-Host "  Installing FFmpeg..." -ForegroundColor Yellow
    
    try {
        $wingetAvailable = Get-Command winget -ErrorAction SilentlyContinue
        if ($wingetAvailable) {
            Write-Host "  Using winget to install FFmpeg..." -ForegroundColor Gray
            $process = Start-Process -FilePath "winget" -ArgumentList "install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements" -Wait -PassThru -NoNewWindow
            
            if ($process.ExitCode -eq 0) {
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
                Write-Host "  [OK] FFmpeg installed via winget" -ForegroundColor Green
                return $true
            }
        }
    } catch {
        Write-Host "  [INFO] winget not available, trying manual download..." -ForegroundColor Gray
    }
    
    try {
        $ffmpegDir = "C:\ffmpeg"
        $ffmpegZip = Join-Path $env:TEMP "ffmpeg-release.zip"
        
        $downloadUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        
        Write-Host "  Downloading from: $downloadUrl" -ForegroundColor Gray
        if ($script:httpProxy) { Write-Host "  Using proxy: $($script:httpProxy)" -ForegroundColor DarkGray }
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequestWithProxy -Uri $downloadUrl -OutFile $ffmpegZip -UseBasicParsing
        
        if (Test-Path $ffmpegZip) {
            Write-Host "  Extracting to $ffmpegDir..." -ForegroundColor Gray
            
            if (-not (Test-Path $ffmpegDir)) {
                New-Item -ItemType Directory -Path $ffmpegDir -Force | Out-Null
            }
            
            Expand-Archive -Path $ffmpegZip -DestinationPath $env:TEMP -Force
            
            $extractedFolder = Get-ChildItem -Path $env:TEMP -Directory -Filter "ffmpeg-*-essentials_build" | Select-Object -First 1
            
            if ($extractedFolder) {
                Copy-Item -Path "$($extractedFolder.FullName)\*" -Destination $ffmpegDir -Recurse -Force
                
                $ffmpegBin = Join-Path $ffmpegDir "bin"
                $currentPath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
                
                if ($currentPath -notlike "*$ffmpegBin*") {
                    [System.Environment]::SetEnvironmentVariable("Path", "$currentPath;$ffmpegBin", "Machine")
                    $env:Path = "$env:Path;$ffmpegBin"
                    Write-Host "  Added $ffmpegBin to system PATH" -ForegroundColor Gray
                }
                
                Remove-Item $ffmpegZip -Force -ErrorAction SilentlyContinue
                Remove-Item $extractedFolder.FullName -Recurse -Force -ErrorAction SilentlyContinue
                
                Write-Host "  [OK] FFmpeg installed to $ffmpegDir" -ForegroundColor Green
                return $true
            }
        }
        
        Write-Host "  [FAIL] FFmpeg download/extraction failed" -ForegroundColor Red
        return $false
    } catch {
        Write-Host "  [FAIL] FFmpeg installation error: $_" -ForegroundColor Red
        return $false
    }
}

Write-Host "Checking FFmpeg..." -ForegroundColor White
$ffmpegInstalled = $false

try {
    $ffmpegVersion = ffmpeg -version 2>&1 | Select-Object -First 1
    if ($ffmpegVersion -match "ffmpeg version") {
        Write-Host "  [OK] $ffmpegVersion" -ForegroundColor Green
        $ffmpegInstalled = $true
    }
} catch {
    Write-Host "  [INFO] FFmpeg is not installed" -ForegroundColor Yellow
}

if (-not $ffmpegInstalled) {
    Write-Host ""
    if ($Silent) {
        Write-Host "  Silent mode: auto-installing FFmpeg..." -ForegroundColor Yellow
        $installChoice = "Y"
    } else {
        $installChoice = Read-Host "  Install FFmpeg now? (Y/N)"
    }

    if ($installChoice -match "^[Yy]") {
        if (Install-FFmpeg) {
            # Verify installation
            try {
                $newFfmpegVersion = ffmpeg -version 2>&1 | Select-Object -First 1
                if ($newFfmpegVersion -match "ffmpeg version") {
                    $ffmpegInstalled = $true
                }
            } catch {
                Write-Host "  [WARN] FFmpeg installed but not yet in PATH" -ForegroundColor Yellow
                Write-Host "         Please restart PowerShell and run this script again" -ForegroundColor Cyan
                $ffmpegInstalled = $true  # Don't fail
            }
        } else {
            Write-Host "  [FAIL] FFmpeg installation failed" -ForegroundColor Red
            Write-Host "         Please install manually from: https://ffmpeg.org/download.html" -ForegroundColor Cyan
            $appChecksFailed = $true
        }
    } else {
        Write-Host "  [SKIP] FFmpeg installation skipped" -ForegroundColor Yellow
        Write-Host "         Please install manually from: https://ffmpeg.org/download.html" -ForegroundColor Cyan
        $appChecksFailed = $true
    }
}

Write-Host ""
Write-Host "Checking DL Streamer..." -ForegroundColor White

$dlStreamerFound = $false
$dlStreamerRequiredVersion = "2026.1.0"

# The full DL Streamer check (detection + version-gate + install/reinstall flow)
# lives in Scripts\check_dlstreamer.ps1. Delegate to it and act on its exit code.
$dlStreamerCheckScript = Join-Path $PSScriptRoot "Scripts\check_dlstreamer.ps1"
if (Test-Path $dlStreamerCheckScript) {
    & $dlStreamerCheckScript -Install -RequiredVersion $dlStreamerRequiredVersion -HttpProxy $script:httpProxy -HttpsProxy $script:httpsProxy
    switch ($LASTEXITCODE) {
        0       { $dlStreamerFound = $true }                          # present and meets required version
        1       { $dlStreamerFound = $true; $appChecksFailed = $true } # present but required reinstall failed
        default { $dlStreamerFound = $false; $appChecksFailed = $true } # not installed / install skipped or failed
    }
} else {
    Write-Host "  [WARN] DL Streamer check script not found at:" -ForegroundColor Yellow
    Write-Host "         $dlStreamerCheckScript" -ForegroundColor DarkYellow
    Write-Host "         Skipping DL Streamer verification." -ForegroundColor DarkYellow
    $appChecksFailed = $true
}

if ($appChecksFailed) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  APPLICATION DEPENDENCIES MISSING" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install the missing dependencies:" -ForegroundColor Yellow
    Write-Host ""
    
    if (-not $ffmpegInstalled) {
        Write-Host "  FFmpeg (required for audio processing):" -ForegroundColor White
        Write-Host "    https://ffmpeg.org/download.html" -ForegroundColor Cyan
        Write-Host "    Or: winget install Gyan.FFmpeg" -ForegroundColor Gray
        Write-Host ""
    }
    
    if (-not $dlStreamerFound) {
        Write-Host "  DL Streamer (required for video pipelines):" -ForegroundColor White
        Write-Host "    https://github.com/open-edge-platform/dlstreamer/releases/download/v2026.1.0/dlstreamer-2026.1.0-win64.exe" -ForegroundColor Cyan
        Write-Host "    Download and run the installer" -ForegroundColor Gray
        Write-Host ""
        Write-Host "  Installation Guide:" -ForegroundColor White
        Write-Host "    https://github.com/open-edge-platform/dlstreamer/blob/main/docs/user-guide/get_started/install/install_guide_windows.md" -ForegroundColor Cyan
        Write-Host ""
    }
    
    Write-Host "----------------------------------------" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "WARNING: Some application dependencies are missing." -ForegroundColor Yellow
    Write-Host "         Certain features may not function correctly." -ForegroundColor DarkYellow
    Write-Host ""
    if ($Silent) {
        Write-Host "Silent mode: continuing with missing dependencies..." -ForegroundColor Yellow
        Write-Host ""
    } else {
        $skipChoice = Read-Host "Do you still want to continue with the setup? (Y/N)"

        if ($skipChoice -match "^[Yy]") {
            Write-Host ""
            Write-Host "  Continuing setup with missing dependencies..." -ForegroundColor Yellow
            Write-Host ""
        } else {
            Write-Host ""
            Write-Host "  Setup cancelled. Please install the missing dependencies and try again." -ForegroundColor Gray
            exit 1
        }
    }
} else {
    Write-Host ""
    Write-Host "Application dependencies check passed!" -ForegroundColor Green
    Write-Host ""
}

# ============================================================================
# [3] CONFIGURE SETTINGS
# ============================================================================
Write-Host "[3] CONFIGURE SETTINGS" -ForegroundColor Green
Write-Host "----------------------" -ForegroundColor Green
Write-Host ""

$configPath = Join-Path $ScriptDir "config.yaml"

if (-not (Test-Path $configPath)) {
    Write-Host "ERROR: config.yaml not found at $configPath" -ForegroundColor Red
    exit 1
}

# Read config file
$configContent = Get-Content $configPath -Raw -Encoding UTF8

# Function to update YAML value (simple string replacement)
function Update-YamlValue {
    param(
        [string]$Content,
        [string]$Key,
        [string]$NewValue,
        [string]$Section = ""
    )
    
    if ($Section) {
        # More complex: need to find section and update key within it
        # For simplicity, we'll use regex patterns
        $pattern = "(?<=$Section[\s\S]*?$Key\s*:\s*)\S+"
        return $Content -replace $pattern, $NewValue
    } else {
        $pattern = "(?<=$Key\s*:\s*)\S+"
        return $Content -replace $pattern, $NewValue
    }
}

# ============================================================================
# [3.1] Language & ASR Configuration
# ============================================================================
Write-Host "----------------------------------------" -ForegroundColor DarkGray
Write-Host "[3.1] Language & ASR Configuration" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor DarkGray
Write-Host ""

# Extract current ASR settings from config
$currentAsrProvider = "openai"
if ($configContent -match "asr:\s*\n\s*provider:\s*(\w+)") {
    $currentAsrProvider = $matches[1]
}

$currentAsrModel = "whisper-small"
if ($configContent -match "asr:\s*\n(?:.*\n)*?\s*name:\s*([\w-]+)") {
    $currentAsrModel = $matches[1]
}

$currentAsrDevice = "CPU"
if ($configContent -match "asr:\s*\n(?:.*\n)*?\s*device:\s*(\w+)") {
    $currentAsrDevice = $matches[1]
}

# Display current ASR settings
Write-Host "Current ASR (Speech Recognition) Settings:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Provider: $currentAsrProvider" -ForegroundColor Cyan
Write-Host "  Model:    $currentAsrModel" -ForegroundColor Cyan
Write-Host "  Device:   $currentAsrDevice" -ForegroundColor Cyan
Write-Host ""

# Extract current language value if exists
$languageMatch = [regex]::Match($configContent, "language:\s*(\S+)")
$currentLanguage = if ($languageMatch.Success) { $languageMatch.Groups[1].Value } else { "en" }
Write-Host "Current language: $currentLanguage" -ForegroundColor Cyan
Write-Host ""

# Ask if user wants to change ASR settings
if ($Silent) {
    Write-Host "Silent mode: keeping existing ASR settings" -ForegroundColor Gray
    $changeAsr = "N"
} else {
    $changeAsr = Read-Host "Do you want to change ASR settings? (Y/N)"
}

if ($changeAsr -match "^[Yy]") {
    Write-Host ""
    
    # Language selection
    Write-Host "Select Language:" -ForegroundColor Yellow
    Write-Host "  [1] en - English" -ForegroundColor White
    Write-Host "  [2] zh - Chinese" -ForegroundColor White
    Write-Host "  [N] No change (current: $currentLanguage)" -ForegroundColor White
    $langChoice = Read-Host "Choice (1/2/N)"
    
    if ($langChoice -eq "1") {
        $configContent = $configContent -replace "(language:\s*)\S+", "`${1}en"
        $currentLanguage = "en"
        Write-Host "  [OK] Language set to: en" -ForegroundColor Green
    } elseif ($langChoice -eq "2") {
        $configContent = $configContent -replace "(language:\s*)\S+", "`${1}zh"
        $currentLanguage = "zh"
        Write-Host "  [OK] Language set to: zh" -ForegroundColor Green
    }
    
    Write-Host ""
    
    # ASR Provider selection
    Write-Host "Select ASR Provider:" -ForegroundColor Yellow
    Write-Host "  [1] openai   - OpenAI Whisper (recommended for English)" -ForegroundColor White
    Write-Host "  [2] openvino - Intel OpenVINO optimized" -ForegroundColor White
    Write-Host "  [3] funasr   - FunASR (recommended for Chinese)" -ForegroundColor White
    Write-Host "  [N] No change (current: $currentAsrProvider)" -ForegroundColor White
    $providerChoice = Read-Host "Choice (1/2/3/N)"
    
    $newProvider = $null
    switch ($providerChoice) {
        "1" { $newProvider = "openai" }
        "2" { $newProvider = "openvino" }
        "3" { $newProvider = "funasr" }
    }
    
    if ($newProvider) {
        $configContent = $configContent -replace "(asr:\s*\n\s*provider:\s*)\w+", "`${1}$newProvider"
        $currentAsrProvider = $newProvider
        Write-Host "  [OK] Provider set to: $newProvider" -ForegroundColor Green
    }
    
    Write-Host ""
    
    # ASR Model selection
    Write-Host "Select ASR Model:" -ForegroundColor Yellow
    Write-Host "  [1] whisper-base   - Smaller, faster" -ForegroundColor White
    Write-Host "  [2] whisper-small  - Balanced (recommended)" -ForegroundColor White
    Write-Host "  [3] whisper-medium - Better accuracy" -ForegroundColor White
    Write-Host "  [4] whisper-large  - Best accuracy, slower" -ForegroundColor White
    Write-Host "  [5] paraformer-zh  - Chinese optimized (FunASR)" -ForegroundColor White
    Write-Host "  [N] No change (current: $currentAsrModel)" -ForegroundColor White
    $modelChoice = Read-Host "Choice (1/2/3/4/5/N)"
    
    $newModel = $null
    switch ($modelChoice) {
        "1" { $newModel = "whisper-base" }
        "2" { $newModel = "whisper-small" }
        "3" { $newModel = "whisper-medium" }
        "4" { $newModel = "whisper-large" }
        "5" { $newModel = "paraformer-zh" }
    }
    
    if ($newModel) {
        $configContent = $configContent -replace "(asr:\s*\n(?:.*\n)*?\s*name:\s*)[\w-]+", "`${1}$newModel"
        $currentAsrModel = $newModel
        Write-Host "  [OK] Model set to: $newModel" -ForegroundColor Green
    }
    
    Write-Host ""
    
    # ASR Device selection
    Write-Host "Select ASR Device:" -ForegroundColor Yellow
    Write-Host "  [C] CPU - Recommended, most compatible" -ForegroundColor White
    Write-Host "  [G] GPU - Faster if supported" -ForegroundColor White
    Write-Host "  [N] No change (current: $currentAsrDevice)" -ForegroundColor White
    $deviceChoice = Read-Host "Choice (C/G/N)"
    
    if ($deviceChoice -match "^[Cc]") {
        $configContent = $configContent -replace "(asr:\s*\n(?:.*\n)*?\s*device:\s*)\w+", "`${1}CPU"
        $currentAsrDevice = "CPU"
        Write-Host "  [OK] Device set to: CPU" -ForegroundColor Green
    } elseif ($deviceChoice -match "^[Gg]") {
        $configContent = $configContent -replace "(asr:\s*\n(?:.*\n)*?\s*device:\s*)\w+", "`${1}GPU"
        $currentAsrDevice = "GPU"
        Write-Host "  [OK] Device set to: GPU" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "Final ASR Settings:" -ForegroundColor Cyan
    Write-Host "  Language: $currentLanguage" -ForegroundColor Gray
    Write-Host "  Provider: $currentAsrProvider" -ForegroundColor Gray
    Write-Host "  Model:    $currentAsrModel" -ForegroundColor Gray
    Write-Host "  Device:   $currentAsrDevice" -ForegroundColor Gray
} else {
    Write-Host "ASR settings unchanged." -ForegroundColor Gray
}

Write-Host ""

# ============================================================================
# [3.2] Upload Size Limits
# ============================================================================
Write-Host "----------------------------------------" -ForegroundColor DarkGray
Write-Host "[3.2] Upload Size Limits" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor DarkGray
Write-Host ""

# Extract current values
$docMaxMatch = [regex]::Match($configContent, "document_max_mb:\s*(\d+)")
$videoMaxMatch = [regex]::Match($configContent, "video_max_mb:\s*(\d+)")
$currentDocMax = if ($docMaxMatch.Success) { $docMaxMatch.Groups[1].Value } else { "100" }
$currentVideoMax = if ($videoMaxMatch.Success) { $videoMaxMatch.Groups[1].Value } else { "1024" }

Write-Host "Current upload size limits in config.yaml:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  content_search:" -ForegroundColor White
Write-Host "    storage:" -ForegroundColor White
Write-Host "      document_max_mb: $currentDocMax    # maximum upload size for documents (MB)" -ForegroundColor Gray
Write-Host "      video_max_mb: $currentVideoMax      # maximum upload size for videos (MB)" -ForegroundColor Gray
Write-Host ""

if ($Silent) {
    Write-Host "Silent mode: keeping existing upload size limits" -ForegroundColor Gray
    $changeUploadLimits = "N"
} else {
    $changeUploadLimits = Read-Host "Do you want to change upload size limits? (Y/N)"
}

if ($changeUploadLimits.ToUpper() -eq "Y") {
    Write-Host ""
    $newDocMax = Read-Host "Enter document_max_mb (blank = $currentDocMax)"
    $newVideoMax = Read-Host "Enter video_max_mb (blank = $currentVideoMax)"
    
    if ($newDocMax -and $newDocMax -match "^\d+$") {
        $configContent = $configContent -replace "(document_max_mb:\s*)\d+", "`${1}$newDocMax"
        Write-Host "  document_max_mb set to $newDocMax" -ForegroundColor Gray
    }
    
    if ($newVideoMax -and $newVideoMax -match "^\d+$") {
        $configContent = $configContent -replace "(video_max_mb:\s*)\d+", "`${1}$newVideoMax"
        Write-Host "  video_max_mb set to $newVideoMax" -ForegroundColor Gray
    }
    
    Write-Host "Upload limits updated." -ForegroundColor Green
} else {
    Write-Host "Keeping current upload limits." -ForegroundColor Gray
}

Write-Host ""

# ============================================================================
# [3.3] OCR Configuration
# ============================================================================
Write-Host "----------------------------------------" -ForegroundColor DarkGray
Write-Host "[3.3] OCR Configuration" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor DarkGray
Write-Host ""

# Extract current OCR enabled value
$ocrMatch = [regex]::Match($configContent, "ocr:\s*\n\s*enabled:\s*(true|false)")
$currentOcr = if ($ocrMatch.Success) { $ocrMatch.Groups[1].Value } else { "true" }

Write-Host "Current OCR configuration in config.yaml:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  ocr:" -ForegroundColor White
Write-Host "    enabled: $currentOcr" -ForegroundColor Gray
Write-Host ""

if ($Silent) {
    Write-Host "Silent mode: keeping existing OCR setting" -ForegroundColor Gray
    $changeOcr = "N"
} else {
    $changeOcr = Read-Host "Do you want to change OCR setting? (Y/N)"
}

if ($changeOcr.ToUpper() -eq "Y") {
    Write-Host ""
    Write-Host "OCR Options:" -ForegroundColor Yellow
    Write-Host "  true  - Enable OCR (extracts text from images/PDFs)" -ForegroundColor Gray
    Write-Host "  false - Disable OCR" -ForegroundColor Gray
    Write-Host ""
    
    $newOcr = Read-Host "Enable OCR? (true/false, blank = $currentOcr)"
    
    if ($newOcr.ToLower() -eq "true" -or $newOcr.ToLower() -eq "false") {
        $configContent = $configContent -replace "(ocr:\s*\n\s*enabled:\s*)(true|false)", "`${1}$($newOcr.ToLower())"
        Write-Host "  OCR enabled set to $($newOcr.ToLower())" -ForegroundColor Gray
        Write-Host "OCR configuration updated." -ForegroundColor Green
    } else {
        Write-Host "Keeping current OCR setting." -ForegroundColor Gray
    }
} else {
    Write-Host "Keeping current OCR setting." -ForegroundColor Gray
}

Write-Host ""

# ============================================================================
# [3.4] Board OCR Configuration
# ============================================================================
Write-Host "----------------------------------------" -ForegroundColor DarkGray
Write-Host "[3.4] Board OCR Configuration (IFPD content summary)" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor DarkGray
Write-Host ""

# Extract current Board OCR enabled value
$boardOcrMatch = [regex]::Match($configContent, "board_ocr:\s*\n\s*enabled:\s*(true|false)")
$currentBoardOcr = if ($boardOcrMatch.Success) { $boardOcrMatch.Groups[1].Value } else { "false" }

Write-Host "Current Board OCR configuration in config.yaml:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  board_ocr:" -ForegroundColor White
Write-Host "    enabled: $currentBoardOcr" -ForegroundColor Gray
Write-Host ""
Write-Host "Note: Board OCR requires OCR to be enabled (ocr.enabled: true)." -ForegroundColor Gray
Write-Host ""

if ($Silent) {
    Write-Host "Silent mode: keeping existing Board OCR setting" -ForegroundColor Gray
    $changeBoardOcr = "N"
} else {
    $changeBoardOcr = Read-Host "Do you want to change Board OCR setting? (Y/N)"
}

if ($changeBoardOcr.ToUpper() -eq "Y") {
    Write-Host ""
    Write-Host "Board OCR Options:" -ForegroundColor Yellow
    Write-Host "  true  - Enable Board OCR (extracts text from the teacher's display for summary)" -ForegroundColor Gray
    Write-Host "  false - Disable Board OCR" -ForegroundColor Gray
    Write-Host ""

    $newBoardOcr = Read-Host "Enable Board OCR? (true/false, blank = $currentBoardOcr)"

    if ($newBoardOcr.ToLower() -eq "true" -or $newBoardOcr.ToLower() -eq "false") {
        $configContent = $configContent -replace "(board_ocr:\s*\n\s*enabled:\s*)(true|false)", "`${1}$($newBoardOcr.ToLower())"
        Write-Host "  Board OCR enabled set to $($newBoardOcr.ToLower())" -ForegroundColor Gray
        Write-Host "Board OCR configuration updated." -ForegroundColor Green
    } else {
        Write-Host "Keeping current Board OCR setting." -ForegroundColor Gray
    }
} else {
    Write-Host "Keeping current Board OCR setting." -ForegroundColor Gray
}

Write-Host ""

# ============================================================================
# SAVE CONFIG FILE
# ============================================================================
Write-Host "----------------------------------------" -ForegroundColor DarkGray
Write-Host "Saving configuration..." -ForegroundColor Yellow

Set-Content -Path $configPath -Value $configContent -NoNewline -Encoding UTF8
Write-Host "Configuration saved to: $configPath" -ForegroundColor Green
Write-Host ""

# ============================================================================
# DISPLAY SUMMARY
# ============================================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   CONFIGURATION SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Re-read to show final values
$finalConfig = Get-Content $configPath -Raw -Encoding UTF8

$finalLang = if ($finalConfig -match "language:\s*(\S+)") { $Matches[1] } else { "en (default)" }
$finalProvider = if ($finalConfig -match "asr:[\s\S]*?provider:\s*(\S+)") { $Matches[1] } else { "unknown" }
$finalAsrName = if ($finalConfig -match "asr:[\s\S]*?name:\s*(\S+)") { $Matches[1] } else { "unknown" }
$finalAsrDevice = if ($finalConfig -match "asr:[\s\S]*?device:\s*(\S+)") { $Matches[1] } else { "CPU" }
$finalDocMax = if ($finalConfig -match "document_max_mb:\s*(\d+)") { $Matches[1] } else { "100" }
$finalVideoMax = if ($finalConfig -match "video_max_mb:\s*(\d+)") { $Matches[1] } else { "1024" }
$finalOcr = if ($finalConfig -match "ocr:\s*\n\s*enabled:\s*(true|false)") { $Matches[1] } else { "true" }
$finalBoardOcr = if ($finalConfig -match "board_ocr:\s*\n\s*enabled:\s*(true|false)") { $Matches[1] } else { "false" }

Write-Host "  Language:        $finalLang" -ForegroundColor White
Write-Host "  ASR Provider:    $finalProvider" -ForegroundColor White
Write-Host "  ASR Model:       $finalAsrName" -ForegroundColor White
Write-Host "  ASR Device:      $finalAsrDevice" -ForegroundColor White
Write-Host "  Doc Max (MB):    $finalDocMax" -ForegroundColor White
Write-Host "  Video Max (MB):  $finalVideoMax" -ForegroundColor White
Write-Host "  OCR Enabled:     $finalOcr" -ForegroundColor White
Write-Host "  Board OCR:       $finalBoardOcr" -ForegroundColor White
Write-Host ""

# ============================================================================
# PYTHON VIRTUAL ENVIRONMENTS
# ============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   CREATING VIRTUAL ENVIRONMENTS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$venvBackend = Join-Path (Split-Path $ScriptDir -Parent) "smartclassroom"
$venvContentSearch = Join-Path $ScriptDir "content_search\venv_content_search"

$recreateVenvs = $false
$upgradeVenvs = $false
if ((Test-Path $venvBackend) -or (Test-Path $venvContentSearch)) {
    if ($Silent) {
        Write-Host "Virtual environments exist, using existing (faster startup)" -ForegroundColor Gray
        $recreateVenvs = $false
    } else {
        Write-Host "  [Y] Yes - Recreate venvs (delete and reinstall from scratch)" -ForegroundColor White
        Write-Host "  [U] Upgrade - Keep venvs, upgrade packages via pip (no full reinstall)" -ForegroundColor White
        Write-Host "  [N] No  - Use existing venvs (faster startup)" -ForegroundColor White
        Write-Host ""
        $response = Read-Host "Do you want to reinstall virtual environments? (Y/U/N, default: N)"
        $recreateVenvs = $response.ToUpper() -eq "Y"
        $upgradeVenvs = $response.ToUpper() -eq "U"
        if ($recreateVenvs) {
            Write-Host "Virtual environments will be recreated" -ForegroundColor Yellow
        } elseif ($upgradeVenvs) {
            Write-Host "Virtual environment packages will be upgraded (venvs kept)" -ForegroundColor Yellow
        } else {
            Write-Host "Using existing virtual environments (faster startup)" -ForegroundColor Gray
        }
    }
}
Write-Host ""

Write-Host "Setting up Backend virtual environment..." -ForegroundColor Yellow
if ($recreateVenvs -and (Test-Path $venvBackend)) {
    Remove-Item $venvBackend -Recurse -Force
}
if (-not (Test-Path $venvBackend)) {
    python -m venv $venvBackend
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create Backend venv" -ForegroundColor Red
        exit 1
    }
    Write-Host "Installing Backend dependencies..." -ForegroundColor Yellow
    & "$venvBackend\Scripts\python.exe" -m pip install --upgrade pip --no-input
    & "$venvBackend\Scripts\python.exe" -m pip install -r (Join-Path $ScriptDir "requirements.txt") --no-input
    Write-Host "[OK] Backend dependencies installed" -ForegroundColor Green
} elseif ($upgradeVenvs) {
    Write-Host "Upgrading Backend dependencies (keeping existing venv)..." -ForegroundColor Yellow
    & "$venvBackend\Scripts\python.exe" -m pip install --upgrade pip --no-input
    & "$venvBackend\Scripts\python.exe" -m pip install --upgrade -r (Join-Path $ScriptDir "requirements.txt") --no-input
    Write-Host "[OK] Backend dependencies upgraded" -ForegroundColor Green
} else {
    Write-Host "[OK] Backend venv already exists" -ForegroundColor Green
}
Write-Host ""

Write-Host "Setting up ContentSearch virtual environment..." -ForegroundColor Yellow
if ($recreateVenvs -and (Test-Path $venvContentSearch)) {
    Remove-Item $venvContentSearch -Recurse -Force
}
if (-not (Test-Path $venvContentSearch)) {
    python -m venv $venvContentSearch
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create ContentSearch venv" -ForegroundColor Red
        exit 1
    }
    Write-Host "Installing ContentSearch dependencies..." -ForegroundColor Yellow
    & "$venvContentSearch\Scripts\python.exe" -m pip install --upgrade pip --no-input
    & "$venvContentSearch\Scripts\python.exe" -m pip install -r (Join-Path $ScriptDir "content_search\requirements.txt") --no-input
    Write-Host "[OK] ContentSearch dependencies installed" -ForegroundColor Green
} elseif ($upgradeVenvs) {
    Write-Host "Upgrading ContentSearch dependencies (keeping existing venv)..." -ForegroundColor Yellow
    & "$venvContentSearch\Scripts\python.exe" -m pip install --upgrade pip --no-input
    & "$venvContentSearch\Scripts\python.exe" -m pip install --upgrade -r (Join-Path $ScriptDir "content_search\requirements.txt") --no-input
    Write-Host "[OK] ContentSearch dependencies upgraded" -ForegroundColor Green
} else {
    Write-Host "[OK] ContentSearch venv already exists" -ForegroundColor Green
}
Write-Host ""

# ============================================================================
# SETUP COMPLETE
# ============================================================================
Write-Host "========================================" -ForegroundColor Green
Write-Host "   SETUP COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Smart Classroom setup has finished successfully." -ForegroundColor Green
Write-Host ""
Write-Host "To start the services, run:" -ForegroundColor Yellow
Write-Host "  .\start-smart-classroom.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "Or with options:" -ForegroundColor Gray
Write-Host "  .\start-smart-classroom.ps1 -SkipProxy       # Skip proxy configuration" -ForegroundColor Gray
Write-Host "  .\start-smart-classroom.ps1 -Restart         # Force restart all services" -ForegroundColor Gray
Write-Host ""
