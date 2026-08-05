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

Required only if you need to ingest legacy **.doc/.ppt/.xls** documents; modern formats (`.docx`, `.pptx`, `.xlsx`) do not need it.

LibreOffice setup (install, add `soffice` to `PATH`, and verify) is documented once in the user guide — see [Install LibreOffice](../../../user-guide/advance-setup-guide.md#e-install-libreoffice-optional-feature-dependent). The same `soffice` executable also powers PDF report export.

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
