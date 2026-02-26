# File Ingest & Retrieve

## Setup

### Prepare Python virtual environment

```cmd
cd file_ingest_and_retrieve
python -m venv venv_py310
venv_py310\Scripts\activate
```

**Note:** Currently only Python version 3.10 has been verified on Windows. Please make sure you've installed the right version.

Some dependencies need to be installed manually

```cmd
pip install git+https://github.com/apple/ml-mobileclip.git@c16bfe5a4feb424762d6bdf5245539120a4ce9ef#egg=mobileclip

pip install salesforce-lavis==1.0.2
```

```cmd
pip install -r requirements.txt
```

> **Note:** You may see pip dependency conflict warnings after this step. These are expected and safe to ignore — `salesforce-lavis` declares outdated version constraints, but the versions installed by `requirements.txt` are the correct ones and the service will work correctly.

Refer to [this guide](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/multimodal-embedding-serving/docs/user-guide/wheel-installation.md) to obtain the multimodal-embedding package wheel `multimodal_embedding_serving-0.1.1-py3-none-any.whl`. Please use verified commit `77b812f`.

```cmd
pip install multimodal_embedding_serving-0.1.1-py3-none-any.whl
```

### Install System Dependencies

#### Tesseract OCR for image text extraction

1. Download the latest installer `tesseract-ocr-w64-setup-v5.x.x.exe` (64-bit) from [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run the installer, default installation path: `C:\Program Files\Tesseract-OCR`
3. Add to PATH:
   ```powershell
   # Open PowerShell as Administrator:
   [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\Tesseract-OCR", "Machine")
   ```
4. Verify installation:
   ```powershell
   # Restart PowerShell:
   tesseract --version
   ```

#### Poppler for PDF processing

1. Download Poppler for Windows from [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases/)
2. Extract to "C:\Program Files\poppler"
3. Add to PATH:
   ```powershell
   # Open PowerShell as Administrator:
   [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\poppler\Library\bin", "Machine")
   ```
4. Verify installation:
   ```powershell
   # Restart PowerShell:
   pdftoppm -v
   ```

#### LibreOffice (Optional - legacy .doc/.ppt/.xls support)

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
$env:https_proxy="<your_https_proxy>"
$env:http_proxy="<your_http_proxy>"
$env:no_proxy="localhost,192.0.0.1,0.0.0.0,127.0.0.1"   
$env:no_proxy_env="localhost,192.0.0.1,0.0.0.0,127.0.0.1"
cd ..
uvicorn file_ingest_and_retrieve.server:app --host 0.0.0.0 --port 9990
```

Make sure MinIO and ChromaDB services are also up and running.

## Sample curl commands

- Ingest a file by bucket name + file path in MinIO (Please ensure the file is already uploaded into MinIO)

```bash
curl -X POST "http://127.0.0.1:9990/v1/dataprep/ingest" -H "Content-Type: application/json" -d "{\"bucket_name\": \"<your_bucket_name>\", \"file_path\": \"<your_file_path>\"}"
```

- Retrieve

```bash
curl -X POST "http://127.0.0.1:9990/v1/retrieval" -H "Content-Type: application/json" -d "{\"query\": \"<some_text_description>\", \"max_num_results\": 1}"
```

---

## API Reference

For the full list of endpoints, request/response schemas, and examples, see the [API Guide](API_GUIDE.md).
