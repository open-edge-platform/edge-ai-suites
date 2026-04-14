param(
  [Parameter(Mandatory=$false)]
  [string]$ConfigPath = "config.json",

  [Parameter(Mandatory=$false)]
  [string]$MinioExe = "",

  [Parameter(Mandatory=$false)]
  [string]$DataDir = ""
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ConfigPath)) {
  throw "Config file not found: $ConfigPath"
}

$configRaw = Get-Content -Path $ConfigPath -Raw
$config = $configRaw | ConvertFrom-Json

$minio = $config.minio
if ($null -eq $minio) {
  throw "Missing 'minio' object in config.json. Expected format: { `"minio`": { ... } }"
}

if ([string]::IsNullOrWhiteSpace($MinioExe)) {
  $MinioExe = [string]$minio.minio_exe
}
if ([string]::IsNullOrWhiteSpace($DataDir)) {
  $DataDir = [string]$minio.data_dir
}

if ([string]::IsNullOrWhiteSpace($MinioExe)) {
  $exeNearScript = Join-Path $PSScriptRoot "minio.exe"
  if (Test-Path $exeNearScript) {
    $MinioExe = $exeNearScript
  }
}
if ([string]::IsNullOrWhiteSpace($DataDir)) {
  $DataDir = "C:\Users\Intel\Downloads\minio-data"
}

if (-not (Test-Path $MinioExe)) {
  throw "minio.exe not found: $MinioExe. Set minio.minio_exe in config.json or pass -MinioExe `"C:\path\to\minio.exe`""
}

if (-not (Test-Path $DataDir)) {
  Write-Host "Creating data dir: $DataDir"
  New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
}

$addressFromConfig = $minio.address

$consoleAddressFromConfig = $minio.console_address

if ([string]::IsNullOrWhiteSpace($addressFromConfig)) {
  throw "Missing minio.address in config.json. Example: `"address`": `":9000`""
}
if ([string]::IsNullOrWhiteSpace($consoleAddressFromConfig)) {
  throw "Missing minio.console_address in config.json. Example: `"console_address`": `":9001`""
}

$Address = [string]$addressFromConfig
$ConsoleAddress = [string]$consoleAddressFromConfig

$rootUser = [string]$minio.root_user
$rootPassword = [string]$minio.root_password

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
