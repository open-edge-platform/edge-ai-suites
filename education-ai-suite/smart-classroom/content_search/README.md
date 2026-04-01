# Content Search

Content Search is a core multimodal service designed for smart classroom environments. It enables AI-driven video summarization, document text extraction, and semantic search capabilities.

## Quick Start
### Pre-requisites
**Python 3.12**: Ensure Python 3.12 is installed and added to your system PATH.

**Administrator Privileges**: Open PowerShell as Administrator.

**Enable Long Paths**: To prevent issues with the Windows 260-character path limit, run the following command in an elevated PowerShell:
```PowerShell
New-ItemProperty -Path "HKLM:\System\CurrentControlSet\Control\FileSystem" `
-Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

### Dependencies Installation
We provide a unified installation script that automates the setup of core dependencies.
```PowerShell
# Run the automation script from the content search root with Windows PowerShell
.\install.ps1
```

> Restart your PowerShell terminal to apply those new environment variables.

Verify the installation by running the following commands:
```PowerShell
tesseract --version
```

### Create the Python Environment
Open PowerShell in the project root and run (replace <PythonPath> with your actual python path):
```PowerShell
& "<PythonPath>" -m venv venv_content_search
# Activate
.\venv_content_search\Scripts\Activate.ps1
# Upgrade pip and install requirements
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> To Exit: Simply type `deactivate` in your terminal to leave the virtual environment.

### Launching Services
Once the environment is configured, activate the virtual environment and launch the `Content Search` service:

```PowerShell
# Activate the virtual environment
.\venv_content_search\Scripts\Activate.ps1

# Start all microservices
python .\start_services.py
```

> For the first-time execution, the service may take several minutes to fully start. This is because the system needs to download pre-trained AI models. Please ensure you have a stable internet connection.

> Upon a successful launch, the console output should not contain any "ERROR" logs.

### Termination
To stop the service and all associated microservices, press `Ctrl` + `C` in the terminal window.

## API Endpoints

| Endpoint | Method | Pattern | Description | Documentation |
| :--- | :---: | :---: | :--- | :--- |
| `/api/v1/task/query/{task_id}` | **GET** | SYNC | **Task Status Inspection**: Retrieves real-time metadata for a specific job, including current lifecycle state (e.g. PROCESSING, COMPLETED, FAILED). | [Details](./docs/dev_guide/Content_search_API.md#task-status-polling) |
| `/api/v1/task/list` | **GET** | SYNC | **Batch Task Retrieval**: Queries task records. Supports filtering via query parameters (e.g., `?status=PROCESSING`). | [Details](./docs/dev_guide/Content_search_API.md#get-task-list) |
| `/api/v1/object/ingest-text` | **POST** | ASYNC | **Text-Specific Ingestion**: Processes raw text strings or existing text-based objects in MinIO for semantic indexing. | [Details](./docs/dev_guide/Content_search_API.md#text-file-ingestion) |
| `/api/v1/object/upload-ingest` | **POST** | ASYNC | **Atomic Upload & Ingestion**: Unified workflow for saving files to MinIO and initiating the ingestion pipeline. | [Details](./docs/dev_guide/Content_search_API.md#file-upload-and-ingestion) |
| `/api/v1/object/search` | **POST** | SYNC | **Semantic Content Retrieval**: Executes similarity search across vector collections using natural language or base64 images. | [Details](./docs/dev_guide/Content_search_API.md#retrieve-and-search) |
| `/api/v1/object/download` | **POST** | STREAM | **Original File Download**: Securely fetches the raw source file directly from MinIO via stream-bridging. | [Details](./docs/dev_guide/Content_search_API.md#resource-download-videoimagedocument) |

For detailed descriptions and examples of each endpoint, please refer to the: [Content Search API reference](./docs/dev_guide/Content_search_API.md)
