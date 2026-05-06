# Content Search

Content Search is a core multimodal service designed for smart classroom environments. It enables AI-driven video summarization, document text extraction, and semantic search capabilities.

## Quick Start
### Pre-requisites
**Python 3.12**: 
- Ensure Python 3.12 is installed and added to your system PATH.

**Windows Long Paths Issue**: 

To prevent issues with the Windows 260-character path limit, please choose one of the following:
- Option A (Recommended): Move the project folder to a shallow directory (e.g., `C:\User\CS` or `D:\Projects`).
- Option B: Lift the path limit by running the following command in a PowerShell window with `Administrator` privileges:
```PowerShell
New-ItemProperty -Path "HKLM:\System\CurrentControlSet\Control\FileSystem" `
-Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

**Network Requirement**: 
- Proxy: If your machine is behind a proxy, ensure your environment variables (e.g., `HTTP_PROXY`, `HTTPS_PROXY`) are correctly configured to allow the script to download necessary components.
- Model Downloads: This system downloads pre-trained models (such as CLIP and BGE) from Hugging Face. Ensure your network has stable access to `huggingface.co`.

### Dependencies Installation
We provide a unified installation script that automates the setup of core dependencies.
Run the following script in PowerShell window with `Administrator` privileges:
```PowerShell
# Run the automation script from the Content Search root with Windows PowerShell
.\install.ps1
```
> **Note**: Restart your PowerShell terminal to apply those new environment variables.

Verify the installation by running the following commands:
```PowerShell
tesseract --version
pdftoppm -v
```

### Create Python Virtual Environment
Open PowerShell in the Content Search project root and run (replace <PythonPath> with your actual python path):
```PowerShell
& "<PythonPath>" -m venv venv_content_search
# Activate
.\venv_content_search\Scripts\Activate.ps1
# Upgrade pip and install requirements
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> **To Exit Venv**: Simply type `deactivate` in your terminal to leave the virtual environment.

### Configuration

Before launching, review the `config.yaml` file in the smart-classroom root directory. Key settings for Content Search are under the `content_search` section.

**Video Summarization** uses a Vision Language Model (VLM) to generate text summaries for uploaded videos, enabling text-based search to surface relevant video segments. It can be globally toggled:

```yaml
content_search:
  video_summarization_enabled: true   # set to false to disable globally
```

- When `true` (default): the `vlm` and `preprocess` services are started, and users can control summarization per file via the UI upload table.
- When `false`: the `vlm` and `preprocess` services are **not** started (saving resources). Videos are still ingested for visual search, but no text summaries are generated.

### Launching Content Search Services
Once the environment is configured, activate the virtual environment and launch the Content Search service:

```PowerShell
# Activate the virtual environment
.\venv_content_search\Scripts\Activate.ps1

# Start all microservices
python .\start_services.py
```
> **Note**: For the first-time execution, the service may take several minutes to fully start. This is because the system needs to download pre-trained AI models (such as CLIP, BGE, and Qwen VLM).

The launcher automatically performs health checks on all services. When all services are ready, you will see:
```
[launcher] All 5 services are ready. (startup took XXs)
[launcher] You can use Ctrl+C to stop all services.
```

If any service fails to start, the launcher will report which service(s) failed:
```
[launcher] WARNING: 1 service(s) failed: vlm (not ready after 600s)
[launcher] Check logs in: <path>/content_search/logs/
```

You can also manually verify the service status:
```PowerShell
Invoke-RestMethod -Uri "http://127.0.0.1:9011/api/v1/system/health"
```
> Tip: The default port is `9011`, but this may vary depending on your specific configuration. Please ensure you are using the correct port for your environment.

### Services Termination
To stop the service and all associated microservices, press `Ctrl` + `C` in the launch terminal window.

## API Endpoints

| Endpoint | Method | Pattern | Description | Documentation |
| :--- | :---: | :---: | :--- | :--- |
| `/api/v1/task/query/{task_id}` | **GET** | SYNC | **Task Status Inspection**: Retrieves real-time metadata for a specific job, including current lifecycle state (e.g. `PROCESSING`, `COMPLETED`, `FAILED`). | [Details](./docs/dev_guide/Content_search_API.md#task-status-polling) |
| `/api/v1/task/list` | **GET** | SYNC | **Batch Task Retrieval**: Queries task records. Supports filtering via query parameters (e.g., `?status=PROCESSING`). | [Details](./docs/dev_guide/Content_search_API.md#get-task-list) |
| `/api/v1/object/files/list` | **GET** | SYNC | **Indexed Files Inventory**: Lists all files with their storage and indexing status, including SQLite metadata, LocalStorage availability, and ChromaDB vector counts. | [Details](./docs/dev_guide/Content_search_API.md#list-all-indexed-files) |
| `/api/v1/object/files/{file_hash}` | **DELETE** | SYNC | **Direct File Deletion**: Deletes a file and all associated data (storage, indices, metadata) using the file_hash from the files list. | [Details](./docs/dev_guide/Content_search_API.md#delete-file-by-hash) |
| `/api/v1/object/ingest-text` | **POST** | ASYNC | **Text-Specific Ingestion**: Processes raw text strings or existing text-based objects for semantic indexing. | [Details](./docs/dev_guide/Content_search_API.md#text-file-ingestion) |
| `/api/v1/object/upload-ingest` | **POST** | ASYNC | **Atomic Upload & Ingestion**: Unified workflow for saving files to local storage and initiating the ingestion pipeline. | [Details](./docs/dev_guide/Content_search_API.md#file-upload-and-ingestion) |
| `/api/v1/object/search` | **POST** | SYNC | **Semantic Content Retrieval**: Executes similarity search across vector collections using natural language or base64 images. | [Details](./docs/dev_guide/Content_search_API.md#retrieve-and-search) |
| `/api/v1/object/download` | **POST** | STREAM | **Original File Download**: Securely fetches the raw source file via stream-bridging. | [Details](./docs/dev_guide/Content_search_API.md#resource-download-videoimagedocument) |
| `/api/v1/object/tags` | **GET** | SYNC | **List Tags**: Returns all unique tags assigned to uploaded files. Useful for populating filter dropdowns in the UI. | [Details](./docs/dev_guide/Content_search_API.md#list-tags) |
| `/api/v1/object/cleanup-task/{task_id}` | **DELETE** | SYNC | **Resource & Task Purge**: Irreversibly deletes local storage files, vector indices, and database records for a specific task. | [Details](./docs/dev_guide/Content_search_API.md#cleanup-file-storage-and-record) |
| `/api/v1/system/config` | **GET** | SYNC | **System Configuration**: Returns Content Search model and database configuration, including VLM model, embedding models, reranker model, vector DB connection, and feature flags. | [Details](./docs/dev_guide/Content_search_API.md#get-system-configuration) |

For detailed descriptions and examples of each endpoint, please refer to the: [Content Search API reference](./docs/dev_guide/Content_search_API.md)
