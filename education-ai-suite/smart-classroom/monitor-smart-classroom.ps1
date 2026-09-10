# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# monitor-smart-classroom.ps1 - Start + watchdog for the Smart Classroom stack.
#
# This is the single entry point to run AFTER setup-smart-classroom.ps1:
# it starts the services (silently, non-interactively) and then keeps the
# backend (:8000) alive. Whenever /health stops answering, it CLEANS UP the
# current (possibly half-dead) services and re-runs start-smart-classroom.ps1's
# flow silently, so the stack stays available without any user interaction.
#
# How it works
#   1. On launch it probes GET /health once. If already healthy it just
#      monitors; otherwise it does a clean start immediately.
#   2. Every -IntervalSeconds it probes /health with curl.exe.
#   3. When unhealthy, it waits out a startup grace window (the VLM takes a
#      couple of minutes to load) before acting. If the grace expires and the
#      backend is still down, it kills every Smart Classroom service and
#      re-launches start-smart-classroom.ps1 -Silent, then starts a fresh
#      grace window. This self-heals and never gets permanently stuck.
#
# Usage (PowerShell; self-elevates to Administrator if needed):
#   .\monitor-smart-classroom.ps1
#   .\monitor-smart-classroom.ps1 -IntervalSeconds 5 -StartupGraceSec 300
#   .\monitor-smart-classroom.ps1 -NoWindowsTerminal        # forwarded to the start script
#
# Stop monitoring with Ctrl+C. (Services are left running.)

[CmdletBinding()]
param(
    [string] $HealthUrl        = "http://127.0.0.1:8000/health",
    [int]    $Port             = 8000,
    [int]    $IntervalSeconds  = 5,      # how often to probe /health
    [int]    $HealthTimeoutSec = 5,      # per-probe curl timeout; keep < IntervalSeconds
    [string] $StartScript      = (Join-Path $PSScriptRoot "start-smart-classroom.ps1"),
    [int]    $StartupGraceSec  = 300,    # time allowed for :8000 to come up after a (re)start before retrying
    [string] $LogDir           = (Join-Path $PSScriptRoot "monitor_logs"),
    [switch] $NoElevate,                 # skip self-elevation (for testing under an already-elevated shell)
    [switch] $NoWindowsTerminal          # forwarded to start-smart-classroom.ps1
)

$ErrorActionPreference = "Stop"

# ============================================================================
# WINDOWS-ONLY CHECK (mirrors start-smart-classroom.ps1)
# ============================================================================
$IsWindowsOS = $IsWindows -or ($PSVersionTable.PSVersion.Major -lt 6) -or ($env:OS -eq "Windows_NT")
if (-not $IsWindowsOS) {
    Write-Host "ERROR: This script is designed for Windows only." -ForegroundColor Red
    exit 1
}

# ============================================================================
# AUTO-ELEVATE TO ADMINISTRATOR
# ============================================================================
# Runs the whole watchdog elevated so every triggered restart inherits that
# token instead of popping an interactive UAC prompt (which would silently
# hang an unattended monitor loop waiting for someone to click "Yes").
if (-not $NoElevate) {
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Write-Host "Requesting Administrator privileges..." -ForegroundColor Yellow
        $argList = "-NoExit -ExecutionPolicy Bypass -File `"$PSCommandPath`" -NoElevate"
        $argList += " -HealthUrl `"$HealthUrl`" -Port $Port -IntervalSeconds $IntervalSeconds -HealthTimeoutSec $HealthTimeoutSec"
        $argList += " -StartScript `"$StartScript`" -StartupGraceSec $StartupGraceSec -LogDir `"$LogDir`""
        if ($NoWindowsTerminal) { $argList += " -NoWindowsTerminal" }
        try {
            Start-Process powershell -Verb RunAs -ArgumentList $argList
            Write-Host "Elevated window launched. You can close this window." -ForegroundColor Green
            exit 0
        } catch {
            Write-Host "Failed to elevate. Please run as Administrator manually." -ForegroundColor Red
            exit 1
        }
    }
}

# ============================================================================
# SETUP
# ============================================================================
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: curl.exe not found on PATH." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path -LiteralPath $StartScript)) {
    Write-Host "ERROR: start script not found: $StartScript" -ForegroundColor Red
    exit 1
}
$StartScript = (Resolve-Path -LiteralPath $StartScript).Path

if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$logPath = Join-Path $LogDir ("monitor_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

function Write-Log {
    param([string] $Text, [string] $Color = "Gray")
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Text
    Write-Host $line -ForegroundColor $Color
    Add-Content -LiteralPath $logPath -Value $line
}

function Test-BackendHealth {
    param([string] $Url, [int] $TimeoutSec)
    # --noproxy '*' makes this probe immune to whatever HTTP_PROXY/NO_PROXY
    # happen to be set -- a proxy that doesn't exempt localhost is exactly the
    # kind of thing that would otherwise make a healthy backend look
    # "unhealthy" and trigger needless restarts.
    $code = & curl.exe -s -m $TimeoutSec --noproxy '*' -o NUL -w "%{http_code}" $Url 2>$null
    $exitCode = $LASTEXITCODE
    $httpCode = 0
    if ($code -match "^\d+$") { $httpCode = [int]$code }
    return [pscustomobject]@{
        Healthy  = ($exitCode -eq 0 -and $httpCode -eq 200)
        HttpCode = $httpCode
        CurlExit = $exitCode
    }
}

# ============================================================================
# CLEANUP - stop every Smart Classroom service before a fresh start
# ============================================================================
# Mirrors the spirit of start-smart-classroom.ps1's Stop-AllServices, but is
# self-contained so the monitor never depends on the start script to tear down
# a wedged stack. Kills by port first (unambiguously ours), then sweeps any
# Smart Classroom python/node processes that crashed without freeing their
# port. Scoped to SC paths/patterns so unrelated python/node is left alone.
$script:ScPorts = @(8000, 9011, 9902, 9012, 5173, 9090, 9900, 8001, 9990)

function Stop-ProcessTree {
    param([int] $ProcId)
    try {
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcId" -ErrorAction SilentlyContinue |
            ForEach-Object { Stop-ProcessTree -ProcId $_.ProcessId }
    } catch {}
    try { Stop-Process -Id $ProcId -Force -ErrorAction SilentlyContinue } catch {}
}

function Stop-SmartClassroomServices {
    Write-Log "Cleaning up existing Smart Classroom services..." "Yellow"

    # 1) Kill whatever holds a known Smart Classroom port.
    foreach ($p in $script:ScPorts) {
        try {
            $conns = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue
            if ($conns) {
                $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
                foreach ($procId in $procIds) {
                    if ($procId -and $procId -ne 0) {
                        Write-Log ("  port {0}: stopping PID {1}" -f $p, $procId)
                        Stop-ProcessTree -ProcId $procId
                    }
                }
            }
        } catch {}
    }

    # 2) Sweep Smart Classroom python/node that crashed without freeing a port.
    $scPatterns = @("smartclassroom", "venv_content_search", "main.py",
                    "start_services.py", "layout_detection", "\ui\", "vite", "5173")
    try {
        Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='node.exe' OR Name='npm.exe'" -ErrorAction SilentlyContinue |
            ForEach-Object {
                $cl   = $_.CommandLine
                $path = $_.ExecutablePath
                $hit  = $false
                foreach ($pat in $scPatterns) {
                    if (($cl -and $cl -like "*$pat*") -or ($path -and $path -like "*$pat*")) { $hit = $true; break }
                }
                if ($hit) {
                    Write-Log ("  stopping stray {0} PID {1}" -f $_.Name, $_.ProcessId)
                    Stop-ProcessTree -ProcId $_.ProcessId
                }
            }
    } catch {}

    # 3) Kill the previous launcher window we spawned (if still around).
    if ($script:launcherProc -and -not $script:launcherProc.HasExited) {
        Write-Log ("  stopping previous launcher PID {0}" -f $script:launcherProc.Id)
        Stop-ProcessTree -ProcId $script:launcherProc.Id
    }
    $script:launcherProc = $null

    Start-Sleep -Seconds 2
    Write-Log "Cleanup complete." "Green"
}

# ============================================================================
# START - clean, then launch start-smart-classroom.ps1 silently
# ============================================================================
$script:launcherProc = $null
$script:lastStartAt   = [datetime]"2000-01-01"

function Start-SmartClassroom {
    Stop-SmartClassroomServices

    # -Silent  : fully non-interactive (no proxy/restart prompts, exits 0 once healthy)
    # -SkipProxy: don't prompt; load proxy from .proxy-config
    # -NoElevate: this monitor is already elevated
    # The launcher runs in its own minimized console and exits 0 once the stack
    # is healthy; the backend it spawns (python main.py, started -NoNewWindow)
    # stays attached to that console and keeps running after the launcher exits
    # (verified: a -NoNewWindow child outlives its parent's exit on Windows).
    $argList = @("-ExecutionPolicy", "Bypass", "-File", $StartScript,
                 "-Silent", "-SkipProxy", "-NoElevate")
    if ($NoWindowsTerminal) { $argList += "-NoWindowsTerminal" }

    Write-Log ("Launching silent start: powershell $($argList -join ' ')") "Cyan"
    try {
        $script:launcherProc = Start-Process powershell -ArgumentList $argList -WindowStyle Minimized -PassThru
        $script:lastStartAt  = Get-Date
        Write-Log ("Start launched (PID {0}); allowing up to {1}s for :{2} to come up." -f `
            $script:launcherProc.Id, $StartupGraceSec, $Port) "Green"
    } catch {
        Write-Log ("Failed to launch start-smart-classroom.ps1: $($_.Exception.Message)") "Red"
        $script:lastStartAt = [datetime]"2000-01-01"   # allow an immediate retry next tick
    }
}

# ============================================================================
# MAIN
# ============================================================================
Write-Log "=== monitor-smart-classroom starting ===" "Cyan"
Write-Log ("url=$HealthUrl port=$Port interval=${IntervalSeconds}s health_timeout=${HealthTimeoutSec}s grace=${StartupGraceSec}s") "Cyan"
Write-Log "start script: $StartScript" "Cyan"
Write-Log "log file: $logPath" "Cyan"
Write-Host ""
Write-Host "Press Ctrl+C to stop monitoring (services keep running)." -ForegroundColor DarkGray
Write-Host ""

# Initial state: only (re)start if the backend isn't already healthy, so
# re-running the monitor against a live stack doesn't needlessly bounce it.
$initial = Test-BackendHealth -Url $HealthUrl -TimeoutSec $HealthTimeoutSec
if ($initial.Healthy) {
    Write-Log ("Backend already healthy (http=$($initial.HttpCode)); monitoring.") "Green"
    $wasHealthy = $true
} else {
    Write-Log "Backend not healthy at launch; performing clean start." "Yellow"
    Start-SmartClassroom
    $wasHealthy = $false
}

while ($true) {
    Start-Sleep -Seconds $IntervalSeconds
    $health = Test-BackendHealth -Url $HealthUrl -TimeoutSec $HealthTimeoutSec

    if ($health.Healthy) {
        if ($wasHealthy -ne $true) { Write-Log ("Backend healthy (http=$($health.HttpCode)).") "Green" }
        $wasHealthy = $true
        continue
    }

    $wasHealthy = $false

    # Describe why it's unhealthy (helps diagnose from the log).
    $listening = $null
    try { $listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue } catch {}
    $reason =
        if (-not $listening)             { "nothing listening on port $Port" }
        elseif ($health.CurlExit -eq 28) { "no response within ${HealthTimeoutSec}s (curl timeout)" }
        elseif ($health.CurlExit -ne 0)  { "curl failed (exit $($health.CurlExit))" }
        else                             { "unhealthy http status ($($health.HttpCode))" }

    # Still inside the startup grace window? Give the backend time to load
    # (VLM startup) instead of thrashing restarts.
    $elapsed = ((Get-Date) - $script:lastStartAt).TotalSeconds
    if ($elapsed -lt $StartupGraceSec) {
        Write-Log ("Backend unhealthy ({0}); starting up, {1:N0}/{2}s elapsed - waiting." -f `
            $reason, $elapsed, $StartupGraceSec) "Yellow"
        continue
    }

    # Grace expired and still down -> clean and restart.
    Write-Log ("Backend unhealthy ({0}) and grace expired after {1:N0}s -> clean restart." -f `
        $reason, $elapsed) "Red"
    Start-SmartClassroom
}
