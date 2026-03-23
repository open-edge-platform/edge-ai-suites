# Backend
## Prerequisites
### Hardware & OS
OS: Windows 11 / Linux

Python: 3.12.x

### Infrastructure
#### Redis
```powershell
# Task queuing (v5.0+)
https://github.com/tporadowski/redis/releases
```
#### PostgreSQL
```powershell
# Metadata storage (v16+)
https://www.postgresql.org/download/windows/ 
# passwd: edu-ai port: 5432
```
#### MinIO
MinIO: Large file object storage
Reference MinIO Doc education-ai-suite/content-search/content_search_minio/README.md

## Environment Setup
### Install Conda Environment (Miniforge)
```powershell
https://conda-forge.org/miniforge/
```
### Configure if need
```powershell
# configure .condarc
channels:
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/
  - https://mirrors.ustc.edu.cn/anaconda/cloud/conda-forge/
  - conda-forge
mirrored_channels:
  conda-forge:
    - https://conda.anaconda.org/conda-forge
    - https://prefix.dev/conda-forge
ssl_verify: false
proxy_servers:
  http: http://proxy-dmz.intel.com:911
  https: http://proxy-dmz.intel.com:912
```
### Setup env
```powershell
conda env create -f conda_env.yml
# if conda env not exist
conda env update -n edu-ai -f conda_env.yml
```
### backup env if need
```powershell
conda env export --no-build > conda_env.yml
```

## Prepare 3rdpart modules
```powershell
# 1. enter into ext_components directory
cd ext_components
# 2. configure the conf.ini to the right submodule's path
# 3. create (remove) softlink
conda activate edu-ai
python .\set_submodule.py -create -f .\conf.ini
python .\set_submodule.py -remove -f .\conf.ini
```
The directory will be like:
```bash
tree -L 3 ext_components/
ext_components/
├── readme.md
... ...
├── content_search_minio -> /xx/x/edge-ai-suites/education-ai-suite/content-search/content_search_minio
└── file_ingest_and_retrieve -> /xx/x/edge-ai-suites/education-ai-suite/content-search/file_ingest_and_retrieve
```

## Launch the backend
```powershell
conda activate edu-ai
# Terminal A
& python .\main.py
# Terminal B
& python .\worker_run.py
# Terminal C (optional)
& python .\mock_services\dummy_ai_provider.py
```

## API Usage & Testing
Using curl or postman
### Health check
```powershell
curl --location 'http://127.0.0.1:8000/api/v1/system/health'
```
response example
```json
{
    "status": "healthy",
    "timestamp": 1773293770.3809352,
    "services": {
        "postgres": "online",
        "redis": "online",
        "minio": "online"
    }
}
```
### Other API endpoints

For API details please refer to [API reference](./doc/API-Reference.md)

| Endpoint | Method | Pattern | Description | Status |
| :--- | :---: | :---: | :--- | :---: |
| `/api/v1/system/health` | **GET** | SYNC | Backend app health check | DONE |
| `/api/v1/task/{task_id}` | **GET** | SYNC | Query status of a specific task | DONE |
| `/api/v1/task/tasks` | **GET** | SYNC | Query tasks by conditions (e.g., `?status=PROCESSING`) | WIP |
| `/api/v1/task/cancel/{task_id}` | **POST** | SYNC | Cancel a running task | WIP |
| `/api/v1/task/pause/{task_id}` | **POST** | SYNC | Pause a running task | WIP |
| `/api/v1/task/resume/{task_id}` | **POST** | SYNC | Resume a paused task | WIP |
| `/api/v1/media/files` | **GET** | SYNC | Query files in MinIO with filters | DONE |
| `/api/v1/media/upload` | **POST** | ASYNC | Upload a file to MinIO | DONE |
| `/api/v1/media/ingest` | **POST** | ASYNC | Ingest a specific file from MinIO | WIP |
| `/api/v1/media/upload-ingest` | **POST** | ASYNC | Upload to MinIO and trigger ingestion | DONE |
| `/api/v1/media/search` | **POST** | ASYNC | Search for files based on description | DONE |
| `/api/v1/media/download` | **POST** | STREAM | Download file from MinIO | DONE |
| `/api/v1/video/summarization` | **POST** | STREAM | Generate video summarization | WIP |

## Automated Tests
```powershell
pip install -r .\tests\requirements.txt
pytest .\tests\pytest -v
```

## Debug tools
* pgadmin 4
* tiny RDM
* postman
