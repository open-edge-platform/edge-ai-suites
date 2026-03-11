param(
	[Parameter(Mandatory=$true)][string]$ModelName,
	[string]$HostAddr = "127.0.0.1",
	[int]$Port = 9900,
	[string]$Device = "GPU",
	[string]$WeightFormat = "int8",
	[string]$HfCacheDir = "$PWD\\.cache\\huggingface"
)

$ErrorActionPreference = "Stop"

# Create venv if needed
if (!(Test-Path .\.venv)) {
	python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1

# Install minimal Windows deps (works for CPU/GPU; GPU is selected via VLM_DEVICE)
python -m pip install -r requirements.txt

# Required settings
$env:VLM_MODEL_NAME = $ModelName
$env:VLM_DEVICE = $Device
$env:VLM_COMPRESSION_WEIGHT_FORMAT = $WeightFormat

# Optional logging/config
if (-not $env:VLM_LOG_LEVEL) { $env:VLM_LOG_LEVEL = "info" }

# Cache directories (keeps downloads out of user profile by default)
$env:HF_HOME = $HfCacheDir
$env:HUGGINGFACE_HUB_CACHE = "$HfCacheDir\\hub"
$env:TRANSFORMERS_CACHE = "$HfCacheDir\\transformers"
$env:XDG_CACHE_HOME = "$HfCacheDir"

Write-Host "Starting vlm-openvino-serving on http://$HostAddr`:$Port" -ForegroundColor Cyan
Write-Host "VLM_MODEL_NAME=$($env:VLM_MODEL_NAME)" -ForegroundColor Cyan
Write-Host "VLM_DEVICE=$($env:VLM_DEVICE)" -ForegroundColor Cyan
Write-Host "VLM_COMPRESSION_WEIGHT_FORMAT=$($env:VLM_COMPRESSION_WEIGHT_FORMAT)" -ForegroundColor Cyan

Write-Host "Tip: after start, check health at http://$HostAddr`:$Port/health" -ForegroundColor DarkGray

# Start with uvicorn (recommended on Windows)
python -m uvicorn src.app:app --host $HostAddr --port $Port

