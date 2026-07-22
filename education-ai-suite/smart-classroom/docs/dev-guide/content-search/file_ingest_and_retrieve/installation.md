# Content Search Feature

This file shows steps to set up and run content search feature.
For full develop guide and API Reference, please see the [API Reference](../Content_search_API.md).

## Setup

### Prerequisites

- **Python 3.12** — verified on Windows: https://www.python.org/downloads/

### Install Python Dependencies

```powershell
cd smart-classroom\content_search
python -m venv venv_content_search
.\venv_content_search\Scripts\activate
pip install -r requirements.txt
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
2. Start Video Preprocess on port `8001`
3. Start VLM on port `9900`
4. Start the File Ingest & Retrieve server on port `9990`

All settings (ports, credentials, paths) are read from `../config.yaml`.

---
