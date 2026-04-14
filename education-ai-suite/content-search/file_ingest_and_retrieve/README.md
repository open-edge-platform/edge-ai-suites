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

#### Tesseract OCR for text extraction

This will be enabled with high-resolution mode, for processing PDF file.
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

## Document Parsing Configuration

`DocumentParser` supports two chunking modes that can be selected when initialising the class directly or via `Indexer`.

### Basic (fixed-size) chunking — default

Text is split by the `unstructured` library into fixed-size chunks.

| Parameter | Default | Description |
|---|---|---|
| `chunk_size` | `250` | Maximum characters per chunk |
| `chunk_overlap` | `50` | Overlapping characters between adjacent chunks |
| `use_hi_res_strategy` | `True` | Renders PDF pages as images for Tesseract OCR (slower, higher accuracy); `False` uses fast strategy with OCR only as fallback |
| `ocr_languages` | `["eng", "chi_sim", "chi"]` | Tesseract language codes used for OCR |

### Semantic chunking (optional)

Pass a LlamaIndex-compatible embedding model to `embed_model` to enable `SemanticSplitterNodeParser`. Instead of splitting by a fixed character count, the parser detects natural topic boundaries using embedding similarity, producing semantically coherent chunks.

A bilingual sentence splitter is used internally, supporting both **Chinese** (。！？；……) and **English** (`. ! ?`) punctuation boundaries.

| Parameter | Default | Description |
|---|---|---|
| `embed_model` | `None` | LlamaIndex embedding model instance. When set, semantic chunking is used instead of basic chunking |
| `semantic_buffer_size` | `2` | Number of surrounding sentences compared when detecting a semantic boundary |
| `semantic_breakpoint_percentile` | `85` | Percentile threshold for breakpoint detection; higher value → fewer, larger chunks |
| `semantic_min_chunk_size` | `200` | Minimum characters per chunk; chunks below this threshold are merged into the next chunk |

**Example — enabling semantic chunking in `Indexer`:**

```python
# In indexer.py, pass the embedding model instance to DocumentParser:
self.document_parser = DocumentParser(
    embed_model=self.document_embedding_model,  # LlamaIndex-compatible OpenVINOEmbedding instance
    semantic_breakpoint_percentile=95,
    semantic_min_chunk_size=150,
    use_hi_res_strategy=False,
)
```

> **Note:** When `embed_model` is provided, `chunk_size` and `chunk_overlap` are ignored.

---

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
