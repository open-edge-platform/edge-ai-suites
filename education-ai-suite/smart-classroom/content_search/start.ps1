$ErrorActionPreference = "Stop"

$configPath = (Join-Path $PSScriptRoot "..\config.yaml") -replace '\\', '/'
$venvPython = Join-Path $PSScriptRoot "venv_content_search\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Venv not found. Run install.ps1 first."
    exit 1
}

$python = $venvPython

# Parse config.yaml
$vals = & $python -c "
import yaml, json
with open('$configPath', encoding='utf-8') as f:
    c = yaml.safe_load(f)
cs = c['content_search']
m, ch = cs['minio'], cs['chromadb']
print(json.dumps({
    'chroma_host': ch['host'], 'chroma_port': str(ch['port']), 'chroma_data_dir': ch.get('data_dir') or '',
    'minio_server': m['server'], 'minio_console': m['console_address'],
    'minio_user': m['root_user'], 'minio_pass': m['root_password'],
    'minio_bucket': m.get('bucket') or '',
    'minio_exe': m.get('minio_exe') or '', 'minio_data_dir': m.get('data_dir') or ''
}))
" | ConvertFrom-Json

# --- ChromaDB ---
$chromaDataDir = if ($vals.chroma_data_dir) { $vals.chroma_data_dir } else { Join-Path $PSScriptRoot "chroma_data" }
if (-not (Test-Path $chromaDataDir)) { New-Item -ItemType Directory -Force -Path $chromaDataDir | Out-Null }

$chroma = Join-Path $PSScriptRoot "venv_content_search\Scripts\chroma.exe"
if (-not (Test-Path $chroma)) { $chroma = "chroma" }

Write-Host "Starting ChromaDB on $($vals.chroma_host):$($vals.chroma_port) ..."
Start-Process $chroma -ArgumentList @("run", "--host", $vals.chroma_host, "--port", $vals.chroma_port, "--path", $chromaDataDir)

# --- MinIO ---
$minioExe = if ($vals.minio_exe) { $vals.minio_exe } else { Join-Path $PSScriptRoot "minio.exe" }
$dataDir  = if ($vals.minio_data_dir)  { $vals.minio_data_dir }  else { Join-Path $PSScriptRoot "minio-data" }
if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Force -Path $dataDir | Out-Null }

$env:MINIO_ROOT_USER     = $vals.minio_user
$env:MINIO_ROOT_PASSWORD = $vals.minio_pass

Write-Host "Starting MinIO on $($vals.minio_server) ..."
Start-Process $minioExe -ArgumentList @("server", $dataDir, "--address", $vals.minio_server, "--console-address", $vals.minio_console)

# --- Create MinIO bucket if needed ---
if ($vals.minio_bucket) {
    Write-Host "Waiting for MinIO to be ready..."
    Start-Sleep -Seconds 3
    & $python -c "
from minio import Minio
client = Minio('$($vals.minio_server)', '$($vals.minio_user)', '$($vals.minio_pass)', secure=False)
bucket = '$($vals.minio_bucket)'
if not client.bucket_exists(bucket):
    client.make_bucket(bucket)
    print('Bucket created:', bucket)
else:
    print('Bucket already exists:', bucket)
"
}

# --- File Ingest & Retrieve (uvicorn) ---
# Must run from smart-classroom (parent of content_search)
$env:no_proxy     = "localhost,192.0.0.1,0.0.0.0,127.0.0.1"
$env:no_proxy_env = "localhost,192.0.0.1,0.0.0.0,127.0.0.1"
$uvicorn = Join-Path $PSScriptRoot "venv_content_search\Scripts\uvicorn.exe"
if (-not (Test-Path $uvicorn)) { $uvicorn = "uvicorn" }
$smartClassroomDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Write-Host "Starting File Ingest & Retrieve server on 0.0.0.0:9990 ..."
Start-Process $uvicorn `
    -ArgumentList @("content_search.file_ingest_and_retrieve.server:app", "--host", "0.0.0.0", "--port", "9990") `
    -WorkingDirectory $smartClassroomDir
