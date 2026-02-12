## Setup

### Prepare Python virtual environment

```cmd
python -m venv venv_py310
```

**Note:** Currently only Python version 3.10 has been verified on Windows. Please make sure you've installed the right version.

```cmd
venv_py310\Scripts\activate
pip install -r requirements.txt
```

Refer to [this guide](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/multimodal-embedding-serving/docs/user-guide/wheel-installation.md) to obtain the multimodal-embedding package wheel `multimodal_embedding_serving-0.1.1-py3-none-any.whl`.

```cmd
pip install multimodal_embedding_serving-0.1.1-py3-none-any.whl
```

Some dependencies need to be installed manually

```cmd
pip install git+https://github.com/apple/ml-mobileclip.git@c16bfe5a4feb424762d6bdf5245539120a4ce9ef#egg=mobileclip

pip install salesforce-lavis==1.0.2
```

### Install System Dependencies

#### A. Install Tesseract OCR (for image text extraction)

**Installation:**
1. Download the latest installer from [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
   - Direct link: https://github.com/UB-Mannheim/tesseract/wiki
   - Download: `tesseract-ocr-w64-setup-v5.x.x.exe` (64-bit)

2. Run the installer
   - Default installation path: `C:\Program Files\Tesseract-OCR`

3. Add to PATH:
   ```powershell
   # Open PowerShell as Administrator and run:
   [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\Tesseract-OCR", "Machine")
   ```

4. Verify installation:
   ```powershell
   # Restart PowerShell, then run:
   tesseract --version
   ```

#### B. Install Poppler (for PDF processing)

**Installation:**
1. Download Poppler for Windows from [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases/)
   - Download: `Release-xx.xx.x-x.zip`

2. Extract to a permanent location:
   ```
   C:\Program Files\poppler
   ```

3. Add to PATH:
   ```powershell
   # Open PowerShell as Administrator:
   [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\poppler\Library\bin", "Machine")
   ```

4. Verify installation:
   ```powershell
   # Restart PowerShell, then run:
   pdftoppm -v
   ```

#### C. Install LibreOffice (Optional - for better DOC/PPT conversion)

**Installation:**
1. Download from [LibreOffice website](https://www.libreoffice.org/download/download/)
2. Run the installer (default settings are fine)
3. Installation path is typically: `C:\Program Files\LibreOffice`

The `unstructured` library will automatically detect and use LibreOffice if available.

### Start service

```powershell
$env:https_proxy="<your_https_proxy>"
$env:http_proxy="your_http_proxy"
$env:no_proxy="localhost,192.0.0.1,0.0.0.0,127.0.0.1"   
$env:no_proxy_env="localhost,192.0.0.1,0.0.0.0,127.0.0.1"
uvicorn file_ingest_and_retrieve.server:app --host 0.0.0.0 --port 9990
```

Make sure MinIO and ChromaDB services are also up and running.

### Sample curl commands

- Ingest a file by bucket name + file path in MinIO (Please ensure the file is already upload into MinIO)

```
curl -X POST "http://127.0.0.1:9990/v1/dataprep/ingest" -H "Content-Type: application/json" -d "{\"bucket_name\": \"<your_bucket_name>\", \"file_path\": \"<your_file_path>\"}"
```


- Retrieve

```
curl -X POST "http://127.0.0.1:9990/v1/retrieval" -H "Content-Type: application/json" -d "{\"query\": \"<some_text_description>\", \"max_num_results\": 1}"
```