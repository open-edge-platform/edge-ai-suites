param(
  [Parameter(Mandatory=$false)]
  [string]$ConfigPath = "config.json",

  [Parameter(Mandatory=$false)]
  [string]$MinioExe = "C:\Users\Intel\Downloads\minio.exe",

  [Parameter(Mandatory=$false)]
  [string]$DataDir = "C:\Users\Intel\Downloads\minio-data",

  [Parameter(Mandatory=$false)]
  [string]$Address = ":9000",

  [Parameter(Mandatory=$false)]
  [string]$ConsoleAddress = ":9001"
)

$ErrorActionPreference = "Stop"

# This script does NOT download minio.exe automatically.
# Download it manually from the official MinIO releases page and pass -MinioExe,
# or place it next to this script and use the default.

if (-not (Test-Path $MinioExe)) {
  throw "minio.exe not found: $MinioExe. Download minio.exe first, then pass -MinioExe `"C:\path\to\minio.exe`""
}

if (-not (Test-Path $DataDir)) {
  Write-Host "Creating data dir: $DataDir"
  New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
}

if (-not (Test-Path $ConfigPath)) {
  throw "Config file not found: $ConfigPath"
}

$configRaw = Get-Content -Path $ConfigPath -Raw
$config = $configRaw | ConvertFrom-Json

# Supports both nested { minio: {...} } and flat { MINIO_ROOT_USER: ... }
$minio = $config.minio
if ($null -eq $minio) { $minio = $config }

$rootUser = $minio.root_user
if ($null -eq $rootUser) { $rootUser = $minio.MINIO_ROOT_USER }

$rootPassword = $minio.root_password
if ($null -eq $rootPassword) { $rootPassword = $minio.MINIO_ROOT_PASSWORD }

if ([string]::IsNullOrWhiteSpace($rootUser) -or [string]::IsNullOrWhiteSpace($rootPassword)) {
  throw "Missing root_user/root_password in config.json (minio.root_user/minio.root_password)"
}

$env:MINIO_ROOT_USER = $rootUser
$env:MINIO_ROOT_PASSWORD = $rootPassword

Write-Host "Starting MinIO server with MINIO_ROOT_USER=$rootUser"
Write-Host "  exe:      $MinioExe"
Write-Host "  data dir: $DataDir"
Write-Host "  address:  $Address"
Write-Host "  console:  $ConsoleAddress"

& $MinioExe server $DataDir --address $Address --console-address $ConsoleAddress
