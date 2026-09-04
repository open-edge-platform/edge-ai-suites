#!/usr/bin/env pwsh
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

<#
.SYNOPSIS
    Launches the Smart Classroom desktop app.

.DESCRIPTION
    The desktop app supervises the Python services itself, so this script only
    bootstraps the Node toolchain and hands over. It never elevates: the one
    action that needs Administrator (enabling Windows long paths) raises its own
    UAC prompt from the app's Setup screen.

    Node is required for `npm install` and `npm run build` only. Once node_modules
    and dist exist, the app runs on Electron's own embedded Node.
#>

param(
    [switch]$Dev,
    [switch]$NoAutoStart,
    [switch]$SkipNodeInstall,
    [switch]$Silent,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ui/package.json engines: "^20.19.0 || >=22.12.0"
$NodePackageId = 'OpenJS.NodeJS.LTS'

$IsWindowsOS = $IsWindows -or ($PSVersionTable.PSVersion.Major -lt 6) -or ($env:OS -eq 'Windows_NT')
if (-not $IsWindowsOS) {
    Write-Host 'ERROR: This script is designed for Windows only.' -ForegroundColor Red
    exit 1
}

if ($Help) {
    Write-Host @'
Smart Classroom Desktop App

Usage: ./start-desktop-app.ps1 [-Dev] [-NoAutoStart] [-SkipNodeInstall] [-Silent] [-Help]

Options:
    -Dev               Run the Vite dev server with hot reload (npm run electron:dev)
    -NoAutoStart       Open the app without starting the backend automatically
    -SkipNodeInstall   Fail instead of installing Node.js when it is missing
    -Silent            Skip the proxy prompts and use the saved .proxy-config
    -Help              Show this help message

The UI is rebuilt on every launch.

The app manages the Python services itself. Use its screens for:
    Get Started     overview and initial guidance
    Services        start / stop / restart and live logs
    Configuration   config.yaml, runtime_config.yaml, proxy settings
    Setup           prerequisites, Python environment, models

This script never requests Administrator privileges.
Use ./start-smart-classroom.ps1 for the browser UI with PowerShell-managed services.
'@ -ForegroundColor Cyan
    exit 0
}

$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
$UiDir = Join-Path $ScriptDir 'ui'

Write-Host ''
Write-Host '========================================' -ForegroundColor Cyan
Write-Host '   SMART CLASSROOM DESKTOP APP' -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''

if (-not (Test-Path (Join-Path $UiDir 'package.json'))) {
    Write-Host "ERROR: ui/package.json not found under $ScriptDir" -ForegroundColor Red
    exit 1
}

# ============================================================================
# PROXY
# ============================================================================
# npm, winget and the first-run Electron binary download all need these.
$proxyConfigFile = Join-Path $ScriptDir '.proxy-config'

# StrictMode makes a missing JSON property fatal, so read defensively.
function Get-ProxyField {
    param($Config, [string]$Name)

    if (-not $Config) { return '' }
    $property = $Config.PSObject.Properties[$Name]
    if ($property -and $property.Value) { return [string]$property.Value }
    return ''
}

# A proxy URL may embed credentials; never print them.
function Format-Proxy {
    param([string]$Url)

    return ($Url -replace '://[^@/]+@', '://***@')
}

function Save-ProxyConfig {
    param([string]$Path, [string]$HttpProxy, [string]$HttpsProxy, [string]$NoProxy)

    $json = [pscustomobject]@{
        httpProxy  = $HttpProxy
        httpsProxy = $HttpsProxy
        noProxy    = $NoProxy
    } | ConvertTo-Json

    # The app reads this with JSON.parse, which chokes on a UTF-8 BOM.
    [System.IO.File]::WriteAllText($Path, $json, [System.Text.UTF8Encoding]::new($false))
}

$savedProxy = $null
if (Test-Path $proxyConfigFile) {
    try {
        $savedProxy = Get-Content $proxyConfigFile -Raw | ConvertFrom-Json
    } catch {
        Write-Host '[WARN] Could not read .proxy-config - ignoring it.' -ForegroundColor Yellow
    }
}

$httpProxy = Get-ProxyField $savedProxy 'httpProxy'
$httpsProxy = Get-ProxyField $savedProxy 'httpsProxy'
$noProxy = Get-ProxyField $savedProxy 'noProxy'
$hasSaved = [bool]($httpProxy -or $httpsProxy)

$envHttpProxy = if ($env:HTTP_PROXY) { $env:HTTP_PROXY } elseif ($env:http_proxy) { $env:http_proxy } else { '' }
$envHttpsProxy = if ($env:HTTPS_PROXY) { $env:HTTPS_PROXY } elseif ($env:https_proxy) { $env:https_proxy } else { '' }
$envNoProxy = if ($env:NO_PROXY) { $env:NO_PROXY } elseif ($env:no_proxy) { $env:no_proxy } else { '' }
$hasEnv = [bool]($envHttpProxy -or $envHttpsProxy)

# Read-Host would hang a scheduled or piped run.
if (-not $Silent -and [Environment]::UserInteractive) {
    Write-Host 'PROXY CONFIGURATION' -ForegroundColor Green

    if ($hasSaved) {
        Write-Host '  Saved settings:' -ForegroundColor Cyan
        if ($httpProxy) { Write-Host "    HTTP_PROXY:  $(Format-Proxy $httpProxy)" -ForegroundColor Gray }
        if ($httpsProxy) { Write-Host "    HTTPS_PROXY: $(Format-Proxy $httpsProxy)" -ForegroundColor Gray }
        if ($noProxy) { Write-Host "    NO_PROXY:    $noProxy" -ForegroundColor Gray }
        Write-Host ''
        Write-Host '  [Y] Change these settings' -ForegroundColor White
        Write-Host '  [N] Keep them' -ForegroundColor White
        Write-Host '  [S] No proxy (direct connection)' -ForegroundColor White
    } elseif ($hasEnv) {
        Write-Host '  Nothing saved yet. Found in the environment:' -ForegroundColor Cyan
        if ($envHttpProxy) { Write-Host "    HTTP_PROXY:  $(Format-Proxy $envHttpProxy)" -ForegroundColor Gray }
        if ($envHttpsProxy) { Write-Host "    HTTPS_PROXY: $(Format-Proxy $envHttpsProxy)" -ForegroundColor Gray }
        if ($envNoProxy) { Write-Host "    NO_PROXY:    $envNoProxy" -ForegroundColor Gray }
        Write-Host ''
        Write-Host '  [Y] Enter different settings' -ForegroundColor White
        Write-Host '  [N] Save these to .proxy-config' -ForegroundColor White
        Write-Host '  [S] No proxy (direct connection)' -ForegroundColor White
    } else {
        Write-Host '  No proxy is configured.' -ForegroundColor Gray
        Write-Host ''
        Write-Host '  [Y] Configure a proxy' -ForegroundColor White
        Write-Host '  [N] No proxy (direct connection)' -ForegroundColor White
    }

    Write-Host ''
    $answer = Read-Host 'Choice (Y/N/S)'
    Write-Host ''

    if ($answer -match '^[Yy]') {
        Write-Host 'Press Enter to keep the value shown in brackets.' -ForegroundColor Yellow
        Write-Host '  (Common Intel proxy: http://proxy-iind.intel.com:912)' -ForegroundColor DarkGray
        Write-Host ''

        $newHttp = Read-Host "HTTP_PROXY  [$(Format-Proxy $httpProxy)]"
        $newHttps = Read-Host "HTTPS_PROXY [$(Format-Proxy $httpsProxy)]"
        $newNo = Read-Host "NO_PROXY    [$noProxy]"

        if ($newHttp) { $httpProxy = $newHttp }
        if ($newHttps) { $httpsProxy = $newHttps } elseif (-not $httpsProxy) { $httpsProxy = $httpProxy }
        if ($newNo) { $noProxy = $newNo }

        Save-ProxyConfig -Path $proxyConfigFile -HttpProxy $httpProxy -HttpsProxy $httpsProxy -NoProxy $noProxy
        Write-Host '  Saved to .proxy-config.' -ForegroundColor Green
    } elseif ($answer -match '^[Ss]' -or (-not $hasSaved -and -not $hasEnv)) {
        $httpProxy = ''
        $httpsProxy = ''
        $noProxy = ''
        Save-ProxyConfig -Path $proxyConfigFile -HttpProxy '' -HttpsProxy '' -NoProxy ''
        Write-Host '  No proxy - using a direct connection.' -ForegroundColor Yellow
    } elseif (-not $hasSaved -and $hasEnv) {
        $httpProxy = $envHttpProxy
        $httpsProxy = $envHttpsProxy
        $noProxy = $envNoProxy
        Save-ProxyConfig -Path $proxyConfigFile -HttpProxy $httpProxy -HttpsProxy $httpsProxy -NoProxy $noProxy
        Write-Host '  Environment settings saved to .proxy-config.' -ForegroundColor Green
    }
}

# Applied unconditionally so that choosing "no proxy" also drops any inherited
# variables, instead of silently leaving them in place.
foreach ($name in 'HTTP_PROXY', 'http_proxy') {
    if ($httpProxy) { Set-Item "Env:$name" $httpProxy } else { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
}
foreach ($name in 'HTTPS_PROXY', 'https_proxy') {
    if ($httpsProxy) { Set-Item "Env:$name" $httpsProxy } else { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
}
foreach ($name in 'NO_PROXY', 'no_proxy') {
    if ($noProxy) { Set-Item "Env:$name" $noProxy } else { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
}

$electronProxy = if ($httpsProxy) { $httpsProxy } else { $httpProxy }
if ($electronProxy) {
    $env:ELECTRON_GET_USE_PROXY = 'true'
    $env:GLOBAL_AGENT_HTTPS_PROXY = $electronProxy
    $env:GLOBAL_AGENT_HTTP_PROXY = $electronProxy
    Write-Host "Using proxy: $(Format-Proxy $electronProxy)" -ForegroundColor Gray
} else {
    Write-Host 'No proxy - using a direct connection.' -ForegroundColor Gray
}

# ============================================================================
# NODE TOOLCHAIN
# ============================================================================
function Test-NodeVersion {
    param([string]$Version)

    if ($Version -notmatch '^v?(\d+)\.(\d+)\.(\d+)') { return $false }
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]

    # Mirrors ui/package.json engines: "^20.19.0 || >=22.12.0".
    if ($major -eq 20) { return $minor -ge 19 }
    if ($major -eq 22) { return $minor -ge 12 }
    return $major -gt 22
}

function Get-NodeVersion {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) { return $null }
    try { return (node --version 2>$null) } catch { return $null }
}

function Update-SessionPath {
    $machine = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = @($machine, $user | Where-Object { $_ }) -join ';'
}

# ----------------------------------------------------------------------------
# WinGet bootstrap
# ----------------------------------------------------------------------------

function Install-WinGet {
    # Install or repair the WinGet CLI via the Microsoft.WinGet.Client module.
    $progressPreference = 'silentlyContinue'
    Install-PackageProvider -Name NuGet -Force | Out-Null
    Install-Module -Name Microsoft.WinGet.Client -Force -Repository PSGallery | Out-Null
    Write-Host 'Using Repair-WinGetPackageManager cmdlet to bootstrap WinGet...' -ForegroundColor Gray

    # The source script passes -AllUsers, which needs Administrator. This script
    # never elevates, so ask for it only when already running elevated and fall
    # back to the per-user repair otherwise.
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $isAdmin = ([Security.Principal.WindowsPrincipal] $identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if ($isAdmin) { Repair-WinGetPackageManager -AllUsers } else { Repair-WinGetPackageManager }

    Update-SessionPath
}

function Test-WinGetSourceHealthy {
    # Probe the source with an actual query. A broken source fails with 0x8a15000f /
    # "Failed when opening source(s)", while a healthy source does not.
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        return $false
    }
    $output = winget search --id Git.Git --source winget --accept-source-agreements --disable-interactivity 2>&1
    return (($output | Out-String) -notmatch '0x8a15000f|Failed when opening source')
}

function Repair-WinGetSource {
    if (Test-WinGetSourceHealthy) {
        return $true
    }

    Write-Host 'WinGet source error detected - reinstalling WinGet...' -ForegroundColor Yellow
    Install-WinGet
    winget source reset --force 2>&1 | Out-Host
    winget source update 2>&1 | Out-Host
    if (Test-WinGetSourceHealthy) {
        return $true
    }

    Write-Host 'Warning: WinGet sources are still unhealthy after reinstall; package steps may fail.' -ForegroundColor Yellow
    return $false
}

# Returns $true when winget is usable for a package install.
function Initialize-WinGet {
    try {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            Write-Host 'winget was not found - bootstrapping it...' -ForegroundColor Yellow
            Install-WinGet
        }
        Repair-WinGetSource | Out-Null
    } catch {
        # $ErrorActionPreference is Stop in this script, so a PSGallery outage or
        # a blocked install would abort the launch outright; fall through to the
        # manual-install message instead.
        Write-Host "Could not bootstrap winget: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    return [bool](Get-Command winget -ErrorAction SilentlyContinue)
}

$nodeVersion = Get-NodeVersion

if (-not (Test-NodeVersion $nodeVersion)) {
    if ($nodeVersion) {
        Write-Host "Node.js $nodeVersion is too old (need ^20.19 or >=22.12)." -ForegroundColor Yellow
    } else {
        Write-Host 'Node.js was not found.' -ForegroundColor Yellow
    }

    if ($SkipNodeInstall) {
        Write-Host 'Install it from https://nodejs.org/en/download/ and run this script again.' -ForegroundColor Cyan
        exit 1
    }

    if (-not (Initialize-WinGet)) {
        Write-Host 'ERROR: winget is not available to install Node.js automatically.' -ForegroundColor Red
        Write-Host 'Install Node.js from https://nodejs.org/en/download/ and run this script again.' -ForegroundColor Cyan
        exit 1
    }

    Write-Host "Installing Node.js LTS via winget ($NodePackageId)..." -ForegroundColor Yellow
    Write-Host 'Accept the elevation prompt if Windows asks for it.' -ForegroundColor DarkGray
    winget install -e --id $NodePackageId --source winget --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Host "winget exited with code $LASTEXITCODE." -ForegroundColor Red
        Write-Host 'Install Node.js from https://nodejs.org/en/download/ and run this script again.' -ForegroundColor Cyan
        exit 1
    }

    Update-SessionPath
    $nodeVersion = Get-NodeVersion

    if (-not (Test-NodeVersion $nodeVersion)) {
        Write-Host ''
        Write-Host 'Node.js was installed but is not on PATH in this session.' -ForegroundColor Yellow
        Write-Host 'Close this terminal, open a new one, and run this script again.' -ForegroundColor Cyan
        exit 1
    }
}

Write-Host "Node.js $nodeVersion" -ForegroundColor Gray

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host 'ERROR: node is present but npm is not on PATH.' -ForegroundColor Red
    exit 1
}

# ============================================================================
# BUILD AND LAUNCH
# ============================================================================
Push-Location $UiDir
try {
    # npm rewrites this marker after every install, so comparing it with the
    # lockfile catches a git pull without paying a registry round-trip on every
    # launch (which would also break launching while offline).
    $installMarker = Join-Path $UiDir 'node_modules\.package-lock.json'
    $lockFile = Join-Path $UiDir 'package-lock.json'
    $needsInstall = -not (Test-Path $installMarker)
    if (-not $needsInstall -and (Test-Path $lockFile)) {
        $needsInstall = (Get-Item $lockFile).LastWriteTimeUtc -gt (Get-Item $installMarker).LastWriteTimeUtc
    }

    if ($needsInstall) {
        Write-Host 'Installing Node dependencies...' -ForegroundColor Yellow
        npm install
        if ($LASTEXITCODE -ne 0) { Write-Host 'npm install failed.' -ForegroundColor Red; exit 1 }
    }

    # Dev mode serves from Vite, so a dist build is not needed.
    if (-not $Dev) {
        Write-Host 'Building the UI...' -ForegroundColor Yellow
        npm run build
        if ($LASTEXITCODE -ne 0) { Write-Host 'UI build failed.' -ForegroundColor Red; exit 1 }
    }

    if (-not $NoAutoStart) { $env:SC_AUTO_START_BACKEND = '1' }

    Write-Host ''
    Write-Host 'Starting the desktop app. Services are managed from its Services screen.' -ForegroundColor Green
    Write-Host 'Close the window to stop everything it started.' -ForegroundColor DarkGray
    Write-Host ''

    if ($Dev) {
        npm run electron:dev
    } else {
        & (Join-Path $UiDir 'node_modules\.bin\electron.cmd') (Join-Path $UiDir 'electron\main.cjs')
    }
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
