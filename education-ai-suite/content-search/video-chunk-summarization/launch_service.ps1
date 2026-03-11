param(
	[string]$HostAddr = "127.0.0.1",
	[int]$Port = 8001,
	[string]$VlmEndpoint = "http://127.0.0.1:9900/v1/chat/completions",
	[int]$VlmTimeoutSeconds = 300,
	[int]$ChunkDurationS = 30,
	[int]$ChunkOverlapS = 4,
	[int]$MaxNumFrames = 8,
	[int]$FrameWidth = 0,
	[int]$FrameHeight = 0
)

$ErrorActionPreference = "Stop"

# Create venv if needed
if (!(Test-Path .\.venv)) {
	python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1

# Install deps
python -m pip install -r requirements.txt

# Settings for the preprocess service
$env:VLM_ENDPOINT = "$VlmEndpoint"
$env:VLM_TIMEOUT_SECONDS = "$VlmTimeoutSeconds"
$env:PREPROCESS_CHUNK_DURATION_S = "$ChunkDurationS"
$env:PREPROCESS_CHUNK_OVERLAP_S = "$ChunkOverlapS"
$env:PREPROCESS_MAX_NUM_FRAMES = "$MaxNumFrames"
$env:PREPROCESS_FRAME_WIDTH = "$FrameWidth"
$env:PREPROCESS_FRAME_HEIGHT = "$FrameHeight"
$env:NO_PROXY = "localhost,127.0.0.1"
$env:no_proxy = "localhost,127.0.0.1"

Write-Host "Starting video preprocess service on http://$HostAddr`:$Port" -ForegroundColor Cyan
Write-Host "VLM_ENDPOINT=$($env:VLM_ENDPOINT)" -ForegroundColor Cyan
Write-Host "VLM_TIMEOUT_SECONDS=$($env:VLM_TIMEOUT_SECONDS)" -ForegroundColor Cyan
Write-Host "PREPROCESS_CHUNK_DURATION_S=$($env:PREPROCESS_CHUNK_DURATION_S)" -ForegroundColor Cyan
Write-Host "PREPROCESS_CHUNK_OVERLAP_S=$($env:PREPROCESS_CHUNK_OVERLAP_S)" -ForegroundColor Cyan
Write-Host "PREPROCESS_MAX_NUM_FRAMES=$($env:PREPROCESS_MAX_NUM_FRAMES)" -ForegroundColor Cyan
Write-Host "PREPROCESS_FRAME_WIDTH=$($env:PREPROCESS_FRAME_WIDTH)" -ForegroundColor Cyan
Write-Host "PREPROCESS_FRAME_HEIGHT=$($env:PREPROCESS_FRAME_HEIGHT)" -ForegroundColor Cyan
Write-Host "NO_PROXY=$($env:NO_PROXY)" -ForegroundColor Cyan
Write-Host "Health: http://$HostAddr`:$Port/health" -ForegroundColor DarkGray

# Start with uvicorn
python -m uvicorn video_process_summary:app --host $HostAddr --port $Port
