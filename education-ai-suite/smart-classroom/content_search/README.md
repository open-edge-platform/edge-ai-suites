# Content Search Feature

This file shows steps to set up and run content search feature.
For full develop guide and API Reference, please see the [Dev Guide](docs/dev_guide/).

## Setup

### Prerequisites

- **Python 3.10** — only this version is verified on Windows: https://www.python.org/downloads/
- **Rust compiler** — required by some dependencies: https://rust-lang.org/tools/install
- **Download minio.exe** — Download MinIO executable from https://dl.min.io/server/minio/release/windows-amd64/minio.exe, and place it in content_search/minio_wrapper folder
- **`multimodal_embedding_serving` wheel** — obtain from [this guide](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/multimodal-embedding-serving/docs/user-guide/wheel-installation.md) (use verified commit `77b812f`). Place the `.whl` file in the `content_search/` folder before running `install.ps1`.

### Install System Dependencies

Run `install.ps1` once to set up the environment (requires admin):
- Creates the Python 3.10 venv
- Installs `mobileclip`, `salesforce-lavis`, `requirements.txt`, and the `multimodal_embedding_serving` wheel
- Downloads and installs Tesseract OCR 5.5.0 and adds it to the system PATH
- Downloads and extracts Poppler 25.12.0 and adds it to the system PATH

```powershell
# 1. Install dependencies (once)
cd content_search
.\install.ps1
```

> **Note:** You may see pip dependency conflict warnings during install. These are expected and safe to ignore.

#### LibreOffice (Optional)

This is for legacy **.doc/.ppt/.xls** support, only install if such formats required.

1. Download from [LibreOffice website](https://www.libreoffice.org/download/download/)
2. Run the installer (default settings are fine). Installation path is typically: `C:\Program Files\LibreOffice`
3. Add to PATH:
   ```powershell
   # Open PowerShell as Administrator:
   [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\LibreOffice\program", "Machine")
   ```
4. Verify installation:
   ```python
   import shutil
   shutil.which("soffice") is not None
   ```

## Start service

```powershell
# 1. Optional: set proxy if needed
$env:https_proxy="<your_https_proxy>"
$env:http_proxy="<your_http_proxy>"

# 2. Under content_search foler
.\venv_content_search\Scripts\activate
python .\start_services.py
```

`start_services.py` will:
1. Start ChromaDB
2. Start MinIO
3. Start Video Preprocess on port `8001`
4. Start VLM on port `9900`
5. Start the File Ingest & Retrieve server on port `9990`

All settings (ports, credentials, paths) are read from `../config.yaml`.

---
