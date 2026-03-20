$ErrorActionPreference = "Stop"

function Invoke-Cmd {
    $exe, $rest = $args
    & $exe $rest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# --- Proxy settings ---
Write-Host "HTTP_PROXY  = $env:HTTP_PROXY"
Write-Host "HTTPS_PROXY = $env:HTTPS_PROXY"
Write-Host "NO_PROXY    = $env:NO_PROXY"

$venvDir    = Join-Path $PSScriptRoot "venv_content_search"
$venvPython = Join-Path $PSScriptRoot "venv_content_search\Scripts\python.exe"

# --- Create venv ---
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating venv (Python 3.10 required)..."
    py -3.10 -m venv $venvDir
} else {
    Write-Host "Venv already exists, skipping creation."
}

# --- Install dependencies ---
Write-Host "Upgrading pip..."
Invoke-Cmd $venvPython -m pip install --upgrade pip --quiet

Write-Host "Installing mobileclip..."
Invoke-Cmd $venvPython -m pip install git+https://github.com/apple/ml-mobileclip.git@c16bfe5a4feb424762d6bdf5245539120a4ce9ef#egg=mobileclip --quiet

Write-Host "Installing salesforce-lavis..."
Invoke-Cmd $venvPython -m pip install salesforce-lavis==1.0.2 --quiet

Write-Host "Installing requirements.txt..."
Invoke-Cmd $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt") --quiet

# --- Install multimodal_embedding_serving wheel ---
$whl = Get-ChildItem -Path $PSScriptRoot -Filter "multimodal_embedding_serving*.whl" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $whl) {
    $whl = Get-ChildItem -Path (Join-Path $PSScriptRoot "..") -Filter "multimodal_embedding_serving*.whl" -ErrorAction SilentlyContinue | Select-Object -First 1
}
if ($whl) {
    Write-Host "Installing multimodal_embedding_serving from $($whl.FullName) ..."
    Invoke-Cmd $venvPython -m pip install $whl.FullName --no-deps --quiet
} else {
    Write-Warning "multimodal_embedding_serving wheel not found. Place multimodal_embedding_serving-0.1.1-py3-none-any.whl in content_search/ and re-run."
}

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

Write-Host "Installation complete. Run start.ps1 to launch services."
