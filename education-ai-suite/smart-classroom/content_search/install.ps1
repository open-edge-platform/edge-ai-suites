$ErrorActionPreference = "Stop"

$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[!] Error: Please run this script as Administrator." -ForegroundColor Red
    exit 1
}
function Invoke-Cmd {
    $exe, $rest = $args
    & $exe $rest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-Cmd-Wait {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )
    Write-Host "[*] Executing: $Executable $Arguments" -ForegroundColor Gray
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -Wait -PassThru -NoNewWindow
    if ($process.ExitCode -ne 0) {
        Write-Host "[!] Process failed with exit code $($process.ExitCode)" -ForegroundColor Red
        exit $process.ExitCode
    }
}

# --- Proxy settings ---
Write-Host "HTTP_PROXY  = $env:HTTP_PROXY"
Write-Host "HTTPS_PROXY = $env:HTTPS_PROXY"
Write-Host "NO_PROXY    = $env:NO_PROXY"

# --- Install Tesseract OCR ---
$tesseractExe = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$tesseractDir = "C:\Program Files\Tesseract-OCR"
if (Test-Path $tesseractExe) {
    Write-Host "Tesseract already installed, skipping."
} else {
    $tesseractUrl      = "https://github.com/tesseract-ocr/tesseract/releases/download/5.5.0/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
    $tesseractInstaller = Join-Path $env:TEMP "tesseract-setup.exe"
    Write-Host "Downloading Tesseract OCR..."
    Invoke-WebRequest -Uri $tesseractUrl -OutFile $tesseractInstaller -UseBasicParsing
    Write-Host "Installing Tesseract OCR (silent)..."
    Invoke-Cmd $tesseractInstaller /S
    Remove-Item $tesseractInstaller -Force
    Write-Host "Tesseract installed."
}
# Add to system PATH if not already present
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*Tesseract-OCR*") {
    [Environment]::SetEnvironmentVariable("Path", $currentPath + ";$tesseractDir", "User")
    Write-Host "Tesseract added to user PATH."
} else {
    Write-Host "Tesseract already in user PATH, skipping."
}

# --- Install Poppler ---
$popplerBin = "C:\Program Files\poppler\Library\bin\pdftoppm.exe"
$popplerBinDir = "C:\Program Files\poppler\Library\bin"
if (Test-Path $popplerBin) {
    Write-Host "Poppler already installed, skipping."
} else {
    $popplerUrl = "https://github.com/oschwartz10612/poppler-windows/releases/download/v25.12.0-0/Release-25.12.0-0.zip"
    $popplerZip = Join-Path $env:TEMP "poppler.zip"
    $popplerDest = "C:\Program Files\poppler"
    Write-Host "Downloading Poppler..."
    Invoke-WebRequest -Uri $popplerUrl -OutFile $popplerZip -UseBasicParsing
    Write-Host "Extracting Poppler..."
    Expand-Archive -Path $popplerZip -DestinationPath $env:TEMP\poppler_extracted -Force
    $extracted = Get-ChildItem -Path $env:TEMP\poppler_extracted -Directory | Select-Object -First 1
    Move-Item -Path $extracted.FullName -Destination $popplerDest -Force
    Remove-Item $popplerZip -Force
    Remove-Item $env:TEMP\poppler_extracted -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Poppler installed."
}
# Add to system PATH if not already present
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*poppler*") {
    [Environment]::SetEnvironmentVariable("Path", $currentPath + ";$popplerBinDir", "User")
    Write-Host "Poppler added to user PATH."
} else {
    Write-Host "Poppler already in user PATH, skipping."
}

# --- Download MinIO ---
$minioDir = Join-Path $PSScriptRoot "providers/minio_wrapper"
$minioExe = Join-Path $minioDir "minio.exe"
if (Test-Path $minioExe) {
    Write-Host "minio.exe already exists, skipping download."
} else {
    $minioUrl = "https://dl.min.io/server/minio/release/windows-amd64/minio.exe"
    Write-Host "Downloading minio.exe..."
    if (-not (Test-Path $minioDir)) { New-Item -ItemType Directory -Path $minioDir | Out-Null }
    Invoke-WebRequest -Uri $minioUrl -OutFile $minioExe -UseBasicParsing
    Write-Host "minio.exe downloaded to $minioExe"
}

Write-Host "Installation complete. Run start_services.py to launch services."
