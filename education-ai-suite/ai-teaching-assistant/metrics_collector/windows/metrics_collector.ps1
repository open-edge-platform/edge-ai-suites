# =============================================================================
# metrics_collector.ps1
# Windows-native metrics collector service (no containers)
#
# Endpoints:
#   GET /health        -> {"status":"ok"}
#   GET /metrics       -> time-series payload used by kiosk UI graphs
#   GET /memory        -> latest memory snapshot
#   GET /platform-info -> hardware summary
# =============================================================================

param(
    [int]$Port = 9000,
    [string]$BindAddress = "127.0.0.1",
    [int]$MaxPoints = 600,
    [int]$SampleIntervalSeconds = 1
)

$ErrorActionPreference = "Stop"

$script:Series = @{
    cpu_utilization = New-Object System.Collections.Generic.List[object]
    gpu_utilization = New-Object System.Collections.Generic.List[object]
    npu_utilization = New-Object System.Collections.Generic.List[object]
    memory = New-Object System.Collections.Generic.List[object]
    power = New-Object System.Collections.Generic.List[object]
}
$script:LastSampleAt = [datetime]::MinValue
$script:NpuCounterPath = $null
$script:NpuProbeDone = $false

function Write-Log {
    param([string]$Message)
    $ts = (Get-Date).ToString("HH:mm:ss")
    Write-Host "[$ts] [metrics-collector] $Message"
}

function Add-SeriesPoint {
    param(
        [string]$Key,
        [object]$Point
    )
    $list = $script:Series[$Key]
    $list.Add($Point)
    if ($list.Count -gt $MaxPoints) {
        $list.RemoveAt(0)
    }
}

function Get-CpuUsage {
    try {
        $counter = Get-Counter '\Processor(_Total)\% Processor Time' -ErrorAction Stop
        return [math]::Round([double]$counter.CounterSamples[0].CookedValue, 2)
    }
    catch {
        return 0.0
    }
}

function Get-MemorySnapshot {
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
        $totalGb = [math]::Round(([double]$os.TotalVisibleMemorySize / 1MB), 2)
        $freeGb = [math]::Round(([double]$os.FreePhysicalMemory / 1MB), 2)
        $usedGb = [math]::Round(($totalGb - $freeGb), 2)
        $pct = if ($totalGb -gt 0) { [math]::Round((100.0 * $usedGb / $totalGb), 2) } else { 0.0 }
        return [ordered]@{
            total_gb = $totalGb
            used_gb = $usedGb
            free_gb = $freeGb
            usage_pct = $pct
        }
    }
    catch {
        return [ordered]@{ total_gb = 0.0; used_gb = 0.0; free_gb = 0.0; usage_pct = 0.0 }
    }
}

function Get-GpuUsage {
    try {
        $counter = Get-Counter '\GPU Engine(*)\Utilization Percentage' -ErrorAction Stop
        $samples = @($counter.CounterSamples | Where-Object {
            $_.InstanceName -and $_.InstanceName -notmatch '(?i)npu'
        })
        if ($samples.Count -eq 0) { return 0.0 }
        $sum = ($samples | Measure-Object -Property CookedValue -Sum).Sum
        if ($null -eq $sum) { return 0.0 }
        return [math]::Round([math]::Min([double]$sum, 100.0), 2)
    }
    catch {
        return 0.0
    }
}

function Initialize-NpuCounterPath {
    if ($script:NpuProbeDone) { return }
    $script:NpuProbeDone = $true
    try {
        $listSets = Get-Counter -ListSet * -ErrorAction SilentlyContinue |
            Where-Object { $_.CounterSetName -match '(?i)npu|neural|ai' }

        foreach ($ls in $listSets) {
            $candidate = $ls.PathsWithInstances |
                Where-Object { $_ -match '(?i)utilization|% processor time|% usage|busy' } |
                Select-Object -First 1
            if ($candidate) {
                $script:NpuCounterPath = $candidate
                return
            }
        }
    }
    catch {
        $script:NpuCounterPath = $null
    }
}

function Get-GpuAndNpuUsage {
    $gpu = 0.0
    $npu = 0.0

    # Primary source: GPU Engine counters (single query for both GPU and NPU).
    try {
        $counter = Get-Counter '\GPU Engine(*)\Utilization Percentage' -ErrorAction Stop
        $samples = @($counter.CounterSamples | Where-Object {
            $_.InstanceName
        })

        if ($samples.Count -gt 0) {
            foreach ($sample in $samples) {
                $value = [double]$sample.CookedValue
                if ($sample.InstanceName -match '(?i)npu') {
                    $npu += $value
                }
                else {
                    $gpu += $value
                }
            }
        }
    }
    catch {
        # If GPU counters are unavailable, keep defaults and try dedicated NPU below.
    }

    # Optional fallback for NPU if not exposed via GPU Engine counters.
    if ($npu -le 0.0 -and $script:NpuCounterPath) {
        try {
            $counter = Get-Counter $script:NpuCounterPath -ErrorAction Stop
            $samples = @($counter.CounterSamples)
            if ($samples.Count -gt 0) {
                $avg = ($samples | Measure-Object -Property CookedValue -Average).Average
                if ($null -ne $avg) {
                    $npu = [double]$avg
                }
            }
        }
        catch {
            # Keep default NPU value.
        }
    }

    return [ordered]@{
        gpu = [math]::Round([math]::Min($gpu, 100.0), 2)
        npu = [math]::Round([math]::Min($npu, 100.0), 2)
    }
}

function Get-PlatformInfo {
    $processor = "--"
    $igpu = "--"
    $npu = "--"
    $memory = "--"
    $storage = "--"

    try {
        $cpuObj = Get-CimInstance Win32_Processor -ErrorAction Stop | Select-Object -First 1
        if ($cpuObj.Name) { $processor = $cpuObj.Name }
    }
    catch {}

    try {
        $gpuNames = Get-CimInstance Win32_VideoController -ErrorAction Stop |
            ForEach-Object { $_.Name } |
            Where-Object { $_ } |
            Select-Object -Unique
        if ($gpuNames) { $igpu = ($gpuNames -join "; ") }
    }
    catch {}

    try {
        $npuDevice = Get-CimInstance Win32_PnPEntity -ErrorAction Stop |
            Where-Object { $_.Name -match '(?i)npu|ai boost|neural' } |
            Select-Object -First 1
        if ($npuDevice -and $npuDevice.Name) { $npu = $npuDevice.Name }
    }
    catch {}

    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
        $memory = "{0:N2} GB" -f ([double]$os.TotalVisibleMemorySize / 1MB)
    }
    catch {}

    try {
        $systemDrive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" -ErrorAction Stop
        if ($systemDrive.Size) {
            $storage = "{0:N2} GB" -f ([double]$systemDrive.Size / 1GB)
        }
    }
    catch {}

    return [ordered]@{
        Processor = $processor
        iGPU = $igpu
        NPU = $npu
        Memory = $memory
        Storage = $storage
    }
}

function Add-MetricSample {
    $ts = (Get-Date).ToString("o")
    $cpu = Get-CpuUsage
    $gpuNpu = Get-GpuAndNpuUsage
    $mem = Get-MemorySnapshot

    Add-SeriesPoint -Key 'cpu_utilization' -Point @($ts, $cpu)
    Add-SeriesPoint -Key 'gpu_utilization' -Point @($ts, $gpuNpu.gpu)
    Add-SeriesPoint -Key 'npu_utilization' -Point @($ts, $gpuNpu.npu)
    Add-SeriesPoint -Key 'memory' -Point @($ts, $mem.total_gb, $mem.used_gb, $mem.free_gb, $mem.usage_pct)
    $script:LastSampleAt = Get-Date
}

function Ensure-Sampled {
    $elapsed = (Get-Date) - $script:LastSampleAt
    if ($elapsed.TotalSeconds -ge $SampleIntervalSeconds) {
        Add-MetricSample
    }
}

function Wait-ForContext {
    param(
        [Parameter(Mandatory = $true)]$Listener,
        [int]$PollMilliseconds = 200
    )

    $asyncResult = $Listener.BeginGetContext($null, $null)
    while (-not $asyncResult.AsyncWaitHandle.WaitOne($PollMilliseconds)) {
        Ensure-Sampled
        if (-not $Listener.IsListening) {
            return $null
        }
    }

    return $Listener.EndGetContext($asyncResult)
}

function Build-MetricsPayload {
    $cpu = $script:Series['cpu_utilization'].ToArray()
    $gpu = $script:Series['gpu_utilization'].ToArray()
    $npu = $script:Series['npu_utilization'].ToArray()
    $mem = $script:Series['memory'].ToArray()
    $pwr = $script:Series['power'].ToArray()

    return [ordered]@{
        cpu_utilization = $cpu
        gpu_utilization = $gpu
        npu_utilization = $npu
        memory = $mem
        power = $pwr
    }
}

function Write-JsonResponse {
    param(
        [Parameter(Mandatory = $true)]$Context,
        [int]$StatusCode,
        [Parameter(Mandatory = $true)]$Body
    )

    $json = ($Body | ConvertTo-Json -Depth 8 -Compress)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    $resp = $Context.Response
    $resp.StatusCode = $StatusCode
    $resp.ContentType = "application/json"
    $resp.ContentEncoding = [System.Text.Encoding]::UTF8
    $resp.ContentLength64 = $bytes.LongLength
    try {
        if ($resp.OutputStream.CanWrite) {
            $resp.OutputStream.Write($bytes, 0, $bytes.Length)
        }
    }
    catch [System.Net.HttpListenerException] {
        # Client disconnected before response body was fully written.
    }
    catch [System.IO.IOException] {
        # Network stream closed mid-write.
    }
    finally {
        try { $resp.OutputStream.Close() } catch {}
    }
}

Initialize-NpuCounterPath
Add-MetricSample

$prefix = "http://$BindAddress`:$Port/"
$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add($prefix)

try {
    $listener.Start()
}
catch {
    Write-Host "Failed to start listener on $prefix"
    Write-Host "If access is denied, run as Administrator once and grant URL ACL:"
    Write-Host "  netsh http add urlacl url=$prefix user=$env:USERNAME"
    throw
}

Write-Log "Listening on $prefix"
Write-Log "Endpoints: /health  /metrics  /memory  /platform-info"

while ($listener.IsListening) {
    try {
        Ensure-Sampled
        $context = Wait-ForContext -Listener $listener
        if ($null -eq $context) {
            continue
        }
        $path = $context.Request.Url.AbsolutePath.ToLowerInvariant()

        switch ($path) {
            "/health" {
                Write-JsonResponse -Context $context -StatusCode 200 -Body @{ status = "ok" }
            }
            "/metrics" {
                Ensure-Sampled
                Write-JsonResponse -Context $context -StatusCode 200 -Body (Build-MetricsPayload)
            }
            "/memory" {
                Ensure-Sampled
                $latest = if ($script:Series.memory.Count -gt 0) { $script:Series.memory[$script:Series.memory.Count - 1] } else { @() }
                if ($latest.Count -ge 5) {
                    Write-JsonResponse -Context $context -StatusCode 200 -Body ([ordered]@{
                        timestamp = $latest[0]
                        total_gb = $latest[1]
                        used_gb = $latest[2]
                        free_gb = $latest[3]
                        usage_pct = $latest[4]
                    })
                }
                else {
                    Write-JsonResponse -Context $context -StatusCode 200 -Body @{ error = "no memory data" }
                }
            }
            "/platform-info" {
                Write-JsonResponse -Context $context -StatusCode 200 -Body (Get-PlatformInfo)
            }
            default {
                Write-JsonResponse -Context $context -StatusCode 404 -Body @{ error = "not found"; path = $path }
            }
        }
    }
    catch {
        $etype = $_.Exception.GetType().FullName
        $emsg = $_.Exception.Message
        $stack = $_.ScriptStackTrace
        Write-Log "Request handling error: $etype :: $emsg"
        if ($stack) {
            Write-Log "Stack: $stack"
        }
    }
}
