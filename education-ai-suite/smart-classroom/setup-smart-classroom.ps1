#!/usr/bin/env pwsh
param(
    [switch]$Help,
    [switch]$NoElevate  
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

Usage: ./setup-smart-classroom.ps1 [-Help] [-NoElevate]

Options:
    -Help       Show this help message
    -NoElevate  Skip auto-elevation to Administrator (Windows)

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
  - DL Streamer: Required for video pipelines (v2026.0.0 verified)

Proxy Configuration:
  If behind a corporate firewall, the script will prompt for proxy settings.
  Settings are saved to .proxy-config for future runs.
  Common Intel proxy: http://proxy-iind.intel.com:912

This script will:
  1. Configure proxy for downloads (if needed)
  2. Check system requirements (OS, RAM, Python, Node.js, etc.)
  3. Check application dependencies (FFmpeg, DL Streamer)
  4. Configure smart-classroom settings (language, upload limits, OCR)
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
    if (-not $script:httpProxy -and -not $script:httpsProxy) { Write-Host "    (No proxy configured)" -ForegroundColor Gray }
    Write-Host ""
    
    Write-Host "  [Y] Yes - Change proxy settings" -ForegroundColor White
    Write-Host "  [N] No  - Use saved proxy settings" -ForegroundColor White
    Write-Host "  [S] Skip - No proxy (direct connection)" -ForegroundColor White
    Write-Host ""
    $changeProxy = Read-Host "Do you want to change proxy settings? (Y/N/S)"
    
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
        Write-Host "  Using saved proxy settings." -ForegroundColor Gray
    }
} else {
    Write-Host ""
    Write-Host "  No proxy configuration found." -ForegroundColor Gray
    Write-Host ""
    Write-Host "  [Y] Yes  - Configure proxy" -ForegroundColor White
    Write-Host "  [N] No   - No proxy (direct connection)" -ForegroundColor White
    Write-Host ""
    $configureProxy = Read-Host "Do you want to configure a proxy? (Y/N)"
    
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
        $proxyConfig = @{
            httpProxy = ""
            httpsProxy = ""
            noProxy = ""
        }
        $proxyConfig | ConvertTo-Json | Set-Content $proxyConfigFile
        Write-Host "  No proxy configured. Settings saved." -ForegroundColor Gray
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

Write-Host "System Requirements:" -ForegroundColor Yellow
Write-Host "  OS: Windows 11" -ForegroundColor Gray
Write-Host "  Processor: Intel Core Ultra Series 1, 2, or 3 (with iGPU)" -ForegroundColor Gray
Write-Host "  Memory: 32 GB RAM (minimum)" -ForegroundColor Gray
Write-Host "  Storage: 50 GB free (for models and logs)" -ForegroundColor Gray
Write-Host "  GPU: Intel iGPU (Core Ultra, Arc) for summarization" -ForegroundColor Gray
Write-Host "  NPU: Intel NPU (Core Ultra) for Video pipelines" -ForegroundColor Gray
Write-Host "  NPU Driver: https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html" -ForegroundColor Cyan
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
    
    if ($totalMemGB -ge 32) {
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
        if ($gpu.Name -match "Intel.*(Arc|Iris|UHD|Graphics)") {
            $intelGpuFound = $true
        }
    }
    
    if ($intelGpuFound) {
        $intelGpu = ($gpuList | Where-Object { $_.Name -match "Intel" } | Select-Object -First 1).Name
        Write-Host "  [OK] $intelGpu" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Intel GPU not detected" -ForegroundColor Yellow
        Write-Host "         Found: $($gpuNames -join ', ')" -ForegroundColor DarkYellow
        Write-Host "         Intel iGPU (Core Ultra, Arc) recommended for summarization" -ForegroundColor DarkYellow
        $warnings += "Intel GPU recommended for summarization acceleration"
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
                        Where-Object { $_.FriendlyName -match "Intel.*NPU|Intel.*Neural" }
    
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
    $npuDevices = Get-PnpDevice -Class "System" -ErrorAction SilentlyContinue | 
                  Where-Object { $_.FriendlyName -match "NPU|Neural" }
    
    if (-not $npuDevices) {
        $npuDevices = Get-PnpDevice -ErrorAction SilentlyContinue | 
                      Where-Object { $_.FriendlyName -match "Intel.*NPU|Intel.*Neural" }
    }
    
    if ($npuDevices) {
        $npuName = ($npuDevices | Select-Object -First 1).FriendlyName
        $npuStatus = ($npuDevices | Select-Object -First 1).Status
        if ($npuStatus -eq "OK") {
            Write-Host "  [OK] $npuName" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] $npuName (Status: $npuStatus)" -ForegroundColor Yellow
            Write-Host "         NPU driver may need to be updated" -ForegroundColor DarkYellow
            Write-Host ""
            $updateDriver = Read-Host "  Do you want to update the NPU driver? (Y/N)"
            if ($updateDriver -match "^[Yy]") {
                Install-NPUDriver | Out-Null
            } else {
                $warnings += "NPU detected but status is $npuStatus"
            }
        }
    } else {
        Write-Host "  [WARN] Intel NPU not detected" -ForegroundColor Yellow
        Write-Host "         Intel NPU (Core Ultra Series) recommended for Video pipelines" -ForegroundColor DarkYellow
        Write-Host ""
        $installNpu = Read-Host "  Do you want to install the Intel NPU driver? (Y/N)"
        if ($installNpu -match "^[Yy]") {
            if (-not (Install-NPUDriver)) {
                $warnings += "Intel NPU driver installation pending (restart may be required)"
            }
        } else {
            $warnings += "Intel NPU recommended for Video pipelines"
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
                Write-Host "  NOTE: You may need to restart PowerShell for PATH changes" -ForegroundColor Cyan
                
                Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
                
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
    $installChoice = Read-Host "  Install Python 3.12.10 now? (Y/N)"
    
    if ($installChoice -match "^[Yy]") {
        if (Install-Python312) {
            # Verify installation
            try {
                $newPythonVersion = python --version 2>&1
                if ($newPythonVersion -match "Python 3\.12") {
                    $pythonInstalled = $true
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
    $installChoice = Read-Host "  Install Node.js v22 LTS now? (Y/N)"
    
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
    $continueSetup = Read-Host "Do you still want to continue with the setup? (Y/N)"
    if ($continueSetup -notmatch "^[Yy]") {
        Write-Host ""
        Write-Host "Setup cancelled by user." -ForegroundColor Yellow
        exit 0
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

function Install-DLStreamerDLLs {
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host "  DL Streamer DLLs-Only Installation" -ForegroundColor Cyan
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  This method extracts pre-built DLLs to C:/" -ForegroundColor Gray
    Write-Host "  and configures the PATH environment variable." -ForegroundColor Gray
    Write-Host ""
    
    $dlsVersion = "2026.0.0"
    $zipName = "dlstreamer_dlls_$dlsVersion.zip"
    $downloadUrl = "https://github.com/open-edge-platform/dlstreamer/releases/download/v$dlsVersion/$zipName"
    $extractPath = "C:\"
    $dlstreamerDllPath = "C:\dlls_windows"
    
    try {
        Write-Host "  Step 1: Download DLLs package" -ForegroundColor Yellow
        $zipPath = Join-Path $env:TEMP $zipName
        
        Write-Host "    Downloading from GitHub releases..." -ForegroundColor Gray
        Write-Host "    URL: $downloadUrl" -ForegroundColor DarkGray
        if ($script:httpProxy) { Write-Host "    Using proxy: $($script:httpProxy)" -ForegroundColor DarkGray }
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        
        $downloadSuccess = $false
        
        try {
            Invoke-WebRequestWithProxy -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing
            if (Test-Path $zipPath) {
                $fileSize = (Get-Item $zipPath).Length
                if ($fileSize -gt 1MB) {
                    $downloadSuccess = $true
                    Write-Host "    [OK] Downloaded: $zipName ($([math]::Round($fileSize/1MB, 1)) MB)" -ForegroundColor Green
                } else {
                    Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
                    Write-Host "    [WARN] Download incomplete, trying alternative method..." -ForegroundColor Yellow
                }
            }
        } catch {
            Write-Host "    [WARN] PowerShell download failed: $($_.Exception.Message)" -ForegroundColor Yellow
        }
        
        if (-not $downloadSuccess -and (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
            Write-Host "    Trying curl.exe..." -ForegroundColor Gray
            try {
                $curlArgs = @("-L", "-o", "`"$zipPath`"", "--connect-timeout", "60", "--max-time", "600")
                if ($script:httpProxy) {
                    $curlArgs += @("-x", $script:httpProxy)
                }
                $curlArgs += $downloadUrl
                
                $curlProcess = Start-Process -FilePath "curl.exe" -ArgumentList $curlArgs -Wait -PassThru -NoNewWindow
                
                if ((Test-Path $zipPath) -and ((Get-Item $zipPath).Length -gt 1MB)) {
                    $downloadSuccess = $true
                    $fileSize = (Get-Item $zipPath).Length
                    Write-Host "    [OK] Downloaded with curl: $zipName ($([math]::Round($fileSize/1MB, 1)) MB)" -ForegroundColor Green
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
        
        Write-Host "  Step 2: Extract to C:/" -ForegroundColor Yellow
        
        if (Test-Path $dlstreamerDllPath) {
            Write-Host "    Removing existing folder: $dlstreamerDllPath" -ForegroundColor Gray
            Remove-Item -Path $dlstreamerDllPath -Recurse -Force -ErrorAction SilentlyContinue
        }
        
        Write-Host "    Extracting $zipName to $extractPath..." -ForegroundColor Gray
        try {
            Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
            Write-Host "    [OK] Extracted to: $dlstreamerDllPath" -ForegroundColor Green
        } catch {
            Write-Host "    [FAIL] Extraction failed: $_" -ForegroundColor Red
            Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
            return $false
        }
        
        Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
        
        Write-Host ""
        
        Write-Host "  Step 3: Configure PATH environment variable" -ForegroundColor Yellow
        
        $currentPath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
        
        if ($currentPath -notlike "*$dlstreamerDllPath*") {
            $newPath = "$currentPath;$dlstreamerDllPath"
            [System.Environment]::SetEnvironmentVariable("Path", $newPath, "Machine")
            Write-Host "    [OK] Added to system PATH: $dlstreamerDllPath" -ForegroundColor Green
            
            $env:Path = "$env:Path;$dlstreamerDllPath"
        } else {
            Write-Host "    [OK] Already in system PATH: $dlstreamerDllPath" -ForegroundColor Green
        }
        
        [System.Environment]::SetEnvironmentVariable("DLSTREAMER_DIR", $dlstreamerDllPath, "Machine")
        $env:DLSTREAMER_DIR = $dlstreamerDllPath
        Write-Host "    [OK] Set DLSTREAMER_DIR: $dlstreamerDllPath" -ForegroundColor Green
        
        Write-Host ""
        
        Write-Host "  Step 4: Install Python Dependencies" -ForegroundColor Yellow
        
        $requirementsFile = Join-Path $dlstreamerDllPath "requirements.txt"
        if (Test-Path $requirementsFile) {
            Write-Host "    Installing Python dependencies from requirements.txt..." -ForegroundColor Gray
            try {
                Push-Location $dlstreamerDllPath
                $pipOutput = python -m pip install -r requirements.txt 2>&1
                Pop-Location
                Write-Host "    [OK] Python dependencies installed" -ForegroundColor Green
            } catch {
                Write-Host "    [WARN] Could not install Python dependencies: $_" -ForegroundColor Yellow
                Write-Host "           Run manually: cd `$env:DLSTREAMER_DIR; python -m pip install -r requirements.txt" -ForegroundColor DarkYellow
            }
        } else {
            Write-Host "    [INFO] No requirements.txt found, skipping Python dependencies" -ForegroundColor Gray
        }
        
        Write-Host ""
        
        Write-Host "  Step 5: Run Python Environment Setup Script" -ForegroundColor Yellow
        
        $setupPythonScript = Join-Path $dlstreamerDllPath "setup_dls_env.ps1"
        if (Test-Path $setupPythonScript) {
            Write-Host "    Running setup_dls_env.ps1..." -ForegroundColor Gray
            Write-Host "    This configures PYTHONPATH, PYGI_DLL_DIRS, and GI_TYPELIB_PATH" -ForegroundColor DarkGray
            try {
                & $setupPythonScript
                Write-Host "    [OK] Python environment configured for current session" -ForegroundColor Green
                Write-Host ""
                Write-Host "    Note: Re-run the following script in new PowerShell sessions:" -ForegroundColor DarkYellow
                Write-Host "          $setupPythonScript" -ForegroundColor Cyan
            } catch {
                Write-Host "    [WARN] Could not run setup script: $_" -ForegroundColor Yellow
                Write-Host "           Run manually: & '$setupPythonScript'" -ForegroundColor DarkYellow
            }
        } else {
            Write-Host "    [INFO] setup_dls_env.ps1 not found at: $setupPythonScript" -ForegroundColor Gray
        }
        
        Write-Host ""
        Write-Host "  ============================================" -ForegroundColor Green
        Write-Host "  DL Streamer DLLs Installation Complete!" -ForegroundColor Green
        Write-Host "  ============================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Installation path: $dlstreamerDllPath" -ForegroundColor Gray
        Write-Host "  DLSTREAMER_DIR:    $dlstreamerDllPath" -ForegroundColor Gray
        Write-Host ""
        Write-Host "  For new PowerShell sessions, run:" -ForegroundColor Yellow
        Write-Host "    & `"$setupPythonScript`"" -ForegroundColor Cyan
        Write-Host ""
        
        return $true
        
    } catch {
        Write-Host "    [FAIL] DL Streamer DLLs installation error: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "  Manual Installation:" -ForegroundColor Yellow
        Write-Host "    1. Download: $downloadUrl" -ForegroundColor Cyan
        Write-Host "    2. Extract to C:/" -ForegroundColor Gray
        Write-Host "    3. Add $dlstreamerDllPath to system PATH" -ForegroundColor Gray
        Write-Host ""
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
    $installChoice = Read-Host "  Install FFmpeg now? (Y/N)"
    
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

$dlStreamerPath = $env:DLSTREAMER_DIR
$dlStreamerFound = $false

if ($dlStreamerPath -and (Test-Path $dlStreamerPath)) {
    $dlStreamerFound = $true
    Write-Host "  [OK] DL Streamer found at: $dlStreamerPath" -ForegroundColor Green
} else {
    # Check common installation paths (including DLLs-only extraction path)
    $commonPaths = @(
        "C:\Program Files\Intel\dlstreamer",
        "C:\Intel\dlstreamer",
        "C:\Program Files (x86)\Intel\dlstreamer",
        "C:\dlls_windows"
    )
    
    if ($env:INTEL_OPENVINO_DIR) {
        $commonPaths += "$env:INTEL_OPENVINO_DIR\..\dlstreamer"
    }
    
    foreach ($path in $commonPaths) {
        if (Test-Path $path) {
            $dlStreamerFound = $true
            Write-Host "  [OK] DL Streamer found at: $path" -ForegroundColor Green
            break
        }
    }
}

if (-not $dlStreamerFound) {
    Write-Host "  [INFO] DL Streamer is not installed" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  DL Streamer is required for video analytics pipelines." -ForegroundColor Gray
    Write-Host "  Latest verified version: 2026.0.0" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  This will download dlstreamer_dlls_2026.0.0.zip, extract to C:/," -ForegroundColor Gray
    Write-Host "  and add C:\dlls_windows to the system PATH." -ForegroundColor Gray
    Write-Host ""
    $installChoice = Read-Host "  Install DL Streamer 2026.0.0 now? (Y/N)"
    
    if ($installChoice -match "^[Yy]") {
        if (Install-DLStreamerDLLs) {
            $dlStreamerFound = $true
        } else {
            Write-Host "  [FAIL] DL Streamer DLLs installation failed" -ForegroundColor Red
            Write-Host "         Please download manually from:" -ForegroundColor Cyan
            Write-Host "         https://github.com/open-edge-platform/dlstreamer/releases/download/v2026.0.0/dlstreamer_dlls_2026.0.0.zip" -ForegroundColor Cyan
            Write-Host "         Extract to C:/ and add C:\dlls_windows to PATH" -ForegroundColor Gray
            $appChecksFailed = $true
        }
    } else {
        Write-Host "  [SKIP] DL Streamer installation skipped" -ForegroundColor Yellow
        Write-Host "         Please install manually from: https://github.com/open-edge-platform/dlstreamer/releases" -ForegroundColor Cyan
        $appChecksFailed = $true
    }
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
        Write-Host "    https://github.com/open-edge-platform/dlstreamer/releases" -ForegroundColor Cyan
        Write-Host "    Download dlstreamer_dlls_2026.0.0.zip, extract to C:/, add C:\dlls_windows to PATH" -ForegroundColor Gray
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
$configContent = Get-Content $configPath -Raw

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
$changeAsr = Read-Host "Do you want to change ASR settings? (Y/N)"

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

$changeUploadLimits = Read-Host "Do you want to change upload size limits? (Y/N)"

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

$changeOcr = Read-Host "Do you want to change OCR setting? (Y/N)"

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
# SAVE CONFIG FILE
# ============================================================================
Write-Host "----------------------------------------" -ForegroundColor DarkGray
Write-Host "Saving configuration..." -ForegroundColor Yellow

Set-Content -Path $configPath -Value $configContent -NoNewline
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
$finalConfig = Get-Content $configPath -Raw

$finalLang = if ($finalConfig -match "language:\s*(\S+)") { $Matches[1] } else { "en (default)" }
$finalProvider = if ($finalConfig -match "asr:[\s\S]*?provider:\s*(\S+)") { $Matches[1] } else { "unknown" }
$finalAsrName = if ($finalConfig -match "asr:[\s\S]*?name:\s*(\S+)") { $Matches[1] } else { "unknown" }
$finalAsrDevice = if ($finalConfig -match "asr:[\s\S]*?device:\s*(\S+)") { $Matches[1] } else { "CPU" }
$finalDocMax = if ($finalConfig -match "document_max_mb:\s*(\d+)") { $Matches[1] } else { "100" }
$finalVideoMax = if ($finalConfig -match "video_max_mb:\s*(\d+)") { $Matches[1] } else { "1024" }
$finalOcr = if ($finalConfig -match "ocr:\s*\n\s*enabled:\s*(true|false)") { $Matches[1] } else { "true" }

Write-Host "  Language:        $finalLang" -ForegroundColor White
Write-Host "  ASR Provider:    $finalProvider" -ForegroundColor White
Write-Host "  ASR Model:       $finalAsrName" -ForegroundColor White
Write-Host "  ASR Device:      $finalAsrDevice" -ForegroundColor White
Write-Host "  Doc Max (MB):    $finalDocMax" -ForegroundColor White
Write-Host "  Video Max (MB):  $finalVideoMax" -ForegroundColor White
Write-Host "  OCR Enabled:     $finalOcr" -ForegroundColor White
Write-Host ""

# ============================================================================
# LAUNCH STARTUP SCRIPT
# ============================================================================
Write-Host "========================================" -ForegroundColor Green
Write-Host "   LAUNCHING SMART CLASSROOM" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

$startupScript = Join-Path $ScriptDir "start-smart-classroom.ps1"

if (Test-Path $startupScript) {
    Write-Host "Starting: $startupScript" -ForegroundColor Yellow
    Write-Host ""
    
    # Execute the startup script with -SkipProxy since proxy was already configured in setup
    & $startupScript -SkipProxy
} else {
    Write-Host "ERROR: start-smart-classroom.ps1 not found at:" -ForegroundColor Red
    Write-Host "  $startupScript" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please run it manually:" -ForegroundColor Yellow
    Write-Host "  cd `"$ScriptDir`"" -ForegroundColor Gray
    Write-Host "  .\start-smart-classroom.ps1" -ForegroundColor Gray
    exit 1
}
