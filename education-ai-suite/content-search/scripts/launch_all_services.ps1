param(
    [string]$ConfigPath = "$PSScriptRoot\services_config.json",
    [string[]]$Services = @("minio", "vlm", "preprocess"),
    [string]$ModelName,
    [string]$HostAddr = "127.0.0.1",
    [int]$VlmPort = 9900,
    [int]$PreprocessPort = 8001,
    [string]$Device = "CPU",
    [string]$WeightFormat = "int8",
    [int]$VlmTimeoutSeconds = 300,
    [int]$PreprocessChunkDurationS = 30,
    [int]$PreprocessChunkOverlapS = 4,
    [int]$PreprocessMaxNumFrames = 8,
    [int]$PreprocessFrameWidth = 0,
    [int]$PreprocessFrameHeight = 0,
    [string]$MinioExe = "",
    [string]$MinioDataDir = ""
)

$ErrorActionPreference = "Stop"

function Get-ConfigValue {
    param(
        [object]$Node,
        [string]$Name,
        [object]$DefaultValue = $null
    )
    if ($null -eq $Node) { return $DefaultValue }
    $prop = $Node.PSObject.Properties[$Name]
    if ($null -eq $prop) { return $DefaultValue }
    if ($null -eq $prop.Value) { return $DefaultValue }
    return $prop.Value
}

$cfg = $null
if (Test-Path $ConfigPath) {
    try {
        $cfg = Get-Content -Path $ConfigPath -Raw | ConvertFrom-Json
    } catch {
        throw "Failed to parse config file '$ConfigPath': $($_.Exception.Message)"
    }
} else {
    Write-Host "Config file not found at $ConfigPath. Falling back to CLI args / defaults." -ForegroundColor Yellow
}

$svc = if ($cfg) { $cfg.services } else { $null }

# Merge rules: CLI arg (if provided) > config file > hardcoded default
if (-not $PSBoundParameters.ContainsKey('ModelName')) { $ModelName = [string](Get-ConfigValue $svc 'model_name' $ModelName) }
if (-not $PSBoundParameters.ContainsKey('HostAddr')) { $HostAddr = [string](Get-ConfigValue $svc 'host_addr' $HostAddr) }
if (-not $PSBoundParameters.ContainsKey('VlmPort')) { $VlmPort = [int](Get-ConfigValue $svc 'vlm_port' $VlmPort) }
if (-not $PSBoundParameters.ContainsKey('PreprocessPort')) { $PreprocessPort = [int](Get-ConfigValue $svc 'preprocess_port' $PreprocessPort) }
if (-not $PSBoundParameters.ContainsKey('Device')) { $Device = [string](Get-ConfigValue $svc 'device' $Device) }
if (-not $PSBoundParameters.ContainsKey('WeightFormat')) { $WeightFormat = [string](Get-ConfigValue $svc 'weight_format' $WeightFormat) }
if (-not $PSBoundParameters.ContainsKey('VlmTimeoutSeconds')) { $VlmTimeoutSeconds = [int](Get-ConfigValue $svc 'vlm_timeout_seconds' $VlmTimeoutSeconds) }
if (-not $PSBoundParameters.ContainsKey('PreprocessChunkDurationS')) { $PreprocessChunkDurationS = [int](Get-ConfigValue $svc 'preprocess_chunk_duration_s' $PreprocessChunkDurationS) }
if (-not $PSBoundParameters.ContainsKey('PreprocessChunkOverlapS')) { $PreprocessChunkOverlapS = [int](Get-ConfigValue $svc 'preprocess_chunk_overlap_s' $PreprocessChunkOverlapS) }
if (-not $PSBoundParameters.ContainsKey('PreprocessMaxNumFrames')) { $PreprocessMaxNumFrames = [int](Get-ConfigValue $svc 'preprocess_max_num_frames' $PreprocessMaxNumFrames) }
if (-not $PSBoundParameters.ContainsKey('PreprocessFrameWidth')) { $PreprocessFrameWidth = [int](Get-ConfigValue $svc 'preprocess_frame_width' $PreprocessFrameWidth) }
if (-not $PSBoundParameters.ContainsKey('PreprocessFrameHeight')) { $PreprocessFrameHeight = [int](Get-ConfigValue $svc 'preprocess_frame_height' $PreprocessFrameHeight) }
if (-not $PSBoundParameters.ContainsKey('MinioExe')) { $MinioExe = [string](Get-ConfigValue $svc 'minio_exe' $MinioExe) }
if (-not $PSBoundParameters.ContainsKey('MinioDataDir')) { $MinioDataDir = [string](Get-ConfigValue $svc 'minio_data_dir' $MinioDataDir) }

$requestedServices = @($Services | ForEach-Object { ([string]$_).ToLowerInvariant().Trim() } | Where-Object { $_ -ne "" } | Select-Object -Unique)
if ($requestedServices.Count -eq 0) {
    throw "At least one service is required. Use -Services minio|vlm|preprocess"
}

$validServices = @("minio", "vlm", "preprocess")
$invalidServices = @($requestedServices | Where-Object { $_ -notin $validServices })
if ($invalidServices.Count -gt 0) {
    throw "Invalid -Services value(s): $($invalidServices -join ', '). Allowed: minio, vlm, preprocess"
}

if (($requestedServices -contains "vlm") -and [string]::IsNullOrWhiteSpace($ModelName)) {
    throw "ModelName is required when launching VLM."
}

$repoRoot = Split-Path -Parent $PSScriptRoot

$minioDir = Join-Path $repoRoot "content_search_minio"
$vlmDir = Join-Path $repoRoot "vlm-openvino-serving"
$preDir = Join-Path $repoRoot "video-chunk-summarization"

$minioScript = Join-Path $minioDir "start_minio_server.ps1"
$vlmScript = Join-Path $vlmDir "launch_service.ps1"
$preScript = Join-Path $preDir "launch_service.ps1"
$minioConfigDefault = Join-Path $minioDir "config.json"
$minioConfigRaw = [string](Get-ConfigValue $svc 'minio_config_path' $minioConfigDefault)
if ([string]::IsNullOrWhiteSpace($minioConfigRaw)) {
    $minioConfig = $minioConfigDefault
} elseif ([System.IO.Path]::IsPathRooted($minioConfigRaw)) {
    $minioConfig = $minioConfigRaw
} else {
    $minioConfig = Join-Path $repoRoot $minioConfigRaw
}

if (($requestedServices -contains "minio") -and !(Test-Path $minioScript)) { throw "MinIO script not found: $minioScript" }
if (($requestedServices -contains "vlm") -and !(Test-Path $vlmScript)) { throw "VLM script not found: $vlmScript" }
if (($requestedServices -contains "preprocess") -and !(Test-Path $preScript)) { throw "Preprocess script not found: $preScript" }

$vlmEndpoint = "http://$HostAddr`:$VlmPort/v1/chat/completions"

Write-Host "Launching services: $($requestedServices -join ', ')" -ForegroundColor Cyan

$minioProc = $null
if ($requestedServices -contains "minio") {
    $minioArgs = @(
        "-NoExit",
        "-NoProfile",
        "-ExecutionPolicy", "ByPass",
        "-File", $minioScript,
        "-ConfigPath", $minioConfig
    )
    if (-not [string]::IsNullOrWhiteSpace($MinioExe)) {
        $minioArgs += @("-MinioExe", $MinioExe)
    }
    if (-not [string]::IsNullOrWhiteSpace($MinioDataDir)) {
        $minioArgs += @("-DataDir", $MinioDataDir)
    }
    $minioProc = Start-Process -PassThru -FilePath "powershell.exe" -WorkingDirectory $minioDir -ArgumentList $minioArgs
}

$vlmProc = $null
if ($requestedServices -contains "vlm") {
    $vlmArgs = @(
        "-NoExit",
        "-NoProfile",
        "-ExecutionPolicy", "ByPass",
        "-File", $vlmScript,
        "-ModelName", $ModelName,
        "-HostAddr", $HostAddr,
        "-Port", $VlmPort,
        "-Device", $Device,
        "-WeightFormat", $WeightFormat
    )
    $vlmProc = Start-Process -PassThru -FilePath "powershell.exe" -WorkingDirectory $vlmDir -ArgumentList $vlmArgs
}

$preProc = $null
if ($requestedServices -contains "preprocess") {
    $preArgs = @(
        "-NoExit",
        "-NoProfile",
        "-ExecutionPolicy", "ByPass",
        "-File", $preScript,
        "-HostAddr", $HostAddr,
        "-Port", $PreprocessPort,
        "-VlmEndpoint", $vlmEndpoint,
        "-VlmTimeoutSeconds", $VlmTimeoutSeconds,
        "-ChunkDurationS", $PreprocessChunkDurationS,
        "-ChunkOverlapS", $PreprocessChunkOverlapS,
        "-MaxNumFrames", $PreprocessMaxNumFrames,
        "-FrameWidth", $PreprocessFrameWidth,
        "-FrameHeight", $PreprocessFrameHeight
    )
    $preProc = Start-Process -PassThru -FilePath "powershell.exe" -WorkingDirectory $preDir -ArgumentList $preArgs
}

Write-Host "Started. PIDs => MinIO=$(if ($null -ne $minioProc) { $minioProc.Id } else { '-' }), VLM=$(if ($null -ne $vlmProc) { $vlmProc.Id } else { '-' }), PRE=$(if ($null -ne $preProc) { $preProc.Id } else { '-' })" -ForegroundColor Green
if ($requestedServices -contains "minio") {
    Write-Host "MinIO Service:      http://127.0.0.1:9001 (console, from config.json)" -ForegroundColor DarkGray
}
if ($requestedServices -contains "vlm") {
    Write-Host "VLM Service: http://$HostAddr`:$VlmPort/health" -ForegroundColor DarkGray
}
if ($requestedServices -contains "preprocess") {
    Write-Host "Preprocess Service: http://$HostAddr`:$PreprocessPort/health" -ForegroundColor DarkGray
}
