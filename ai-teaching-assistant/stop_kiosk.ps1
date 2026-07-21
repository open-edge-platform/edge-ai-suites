# =============================================================================
# stop_kiosk.ps1
# Smart Kiosk Assistant - Service Shutdown Script
#
# Gracefully stops all running services
#
# Usage: powershell -ExecutionPolicy Bypass -File stop_kiosk.ps1
# =============================================================================

param(
    [switch]$Force = $false  # Force kill processes
)

$ErrorActionPreference = "Continue"
$WarningPreference = "SilentlyContinue"

# Color output
function Write-Header {
    param([string]$Message)
    Write-Host "`n" -ForegroundColor White
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "=" * 70 -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "[*] $Message" -ForegroundColor Yellow
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Red
}

Write-Header "SMART KIOSK ASSISTANT - SHUTDOWN"

$Services = @("metrics-collector", "text-to-speech", "audio-analyzer", "rag-service", "kiosk-core", "kiosk-ui")
$Ports = @{
    "metrics-collector" = 9000
    "text-to-speech" = 8011
    "audio-analyzer" = 8010
    "rag-service" = 8020
    "kiosk-core" = 8012
    "kiosk-ui" = 7860
}

$StoppedCount = 0

foreach ($Service in $Services) {
    $Port = $Ports[$Service]
    
    try {
        # Find listener PID using PowerShell TCP APIs first, then netstat fallback
        $ProcessIds = @()

        try {
            $Conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
            if ($Conn) {
                $ProcessIds += @($Conn | Select-Object -ExpandProperty OwningProcess)
            }
        }
        catch {}

        if (-not $ProcessIds) {
            $NetstatLines = netstat -ano | Select-String ":$Port " | Select-String "LISTENING"
            foreach ($Line in $NetstatLines) {
                $PidToken = ($Line.ToString().Trim() -split '\s+')[-1]
                if ($PidToken -match '^\d+$') {
                    $ProcessIds += [int]$PidToken
                }
            }
        }

        $ProcessIds = @($ProcessIds | Sort-Object -Unique | Where-Object { $_ -gt 0 })

        if ($ProcessIds.Count -gt 0) {
            foreach ($ProcessId in $ProcessIds) {
                if ($ProcessId -le 4) {
                    Write-Info "$Service is bound by system process PID $ProcessId; skipping"
                    continue
                }

                try {
                    if ($Force) {
                        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
                        Write-Success "$Service (PID $ProcessId) force stopped"
                    }
                    else {
                        Stop-Process -Id $ProcessId -ErrorAction Stop
                        Write-Success "$Service (PID $ProcessId) stopped"
                    }

                    $StoppedCount++
                }
                catch {
                    Write-Error-Custom "Could not stop $Service (PID $ProcessId): $($_.Exception.Message)"
                }
            }
        }
        else {
            Write-Info "$Service is not running"
        }
    }
    catch {
        Write-Error-Custom "Error stopping $Service : $_"
    }
}

Write-Header "SHUTDOWN COMPLETE"
Write-Success "Stopped $StoppedCount service(s)"

Write-Info "All services are now stopped."
Write-Host "`nTo start again, run: powershell -ExecutionPolicy Bypass -File start_kiosk.ps1`n" -ForegroundColor Green

Start-Sleep -Milliseconds 500
