# MinIO (This Folder)

This folder provides:
- A MinIO server start script (Windows PowerShell)
- A Python client wrapper `MinioStore` (a thin wrapper around the MinIO Python SDK)
- A runnable example (examples/)

Goal: other services should depend on `MinioStore` rather than calling the MinIO SDK directly.

## Folder Layout

- `config.json`: MinIO connection + bucket config
- `minio_client.py`: the unified client wrapper (`MinioStore`)
- `start_minio_server.ps1`: starts the MinIO server from config on Windows
- `examples/`: example programs

## 1) Configuration (config.json)

Example:

```json
{
  "minio": {
    "address": ":9000",
    "console_address": ":9001",
    "server": "127.0.0.1:9000",
    "minio_exe": "C:\\Users\\Intel\\Downloads\\minio.exe",
    "data_dir": "C:\\Users\\Intel\\Downloads\\minio-data",
    "root_user": "minioadmin",
    "root_password": "minioadmin",
    "bucket": "content-search",
    "secure": false
  }
}
```

Fields:
- `minio.address`: bind address for the MinIO S3 API (required by `start_minio_server.ps1`)
- `minio.console_address`: bind address for the MinIO Console UI (required by `start_minio_server.ps1`)
- `minio.server`: `host:port` (for example `127.0.0.1:9000`)
- `minio.minio_exe`: MinIO executable path on Windows (for example `C:\Users\Intel\Downloads\minio.exe`)
- `minio.data_dir`: MinIO data directory (for example `C:\Users\Intel\Downloads\minio-data`)
- `minio.root_user` / `minio.root_password`: credentials
- `minio.bucket`: default bucket name
- `minio.secure`: whether to use HTTPS (default `false`)

## 2) Start MinIO Server (Windows)

This folder includes a PowerShell script: `start_minio_server.ps1`.

Prerequisite: you must download `minio.exe` yourself (the script does not download it).
https://dl.min.io/server/minio/release/windows-amd64/minio.exe

Recommended (PowerShell):

```powershell
cd <this-folder>
.\start_minio_server.ps1
```

Optional parameters:
- `-ConfigPath`: default `config.json`
- `-MinioExe`: override `minio.minio_exe`
- `-DataDir`: override `minio.data_dir`

Precedence:
1. CLI args (`-MinioExe`, `-DataDir`)
2. `config.json` (`minio.minio_exe`, `minio.data_dir`)
3. Built-in fallback (`minio.exe` next to script for exe; `C:\Users\Intel\Downloads\minio-data` for data dir)

The script reads `root_user/root_password` from `config.json` and sets:
- `MINIO_ROOT_USER`
- `MINIO_ROOT_PASSWORD`

## 3) Python Environment Setup on Windows for minIO Client

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 4) Python: MinioStore (minio_client.py)

### 4.1 Initialization

Most common (recommended):

```python
from content_search_minio.minio_client import MinioStore

store = MinioStore.from_config()
store.ensure_bucket()
```

Notes:
- `from_config()` reads `config.json` via the lookup rules above and creates the MinIO SDK client
- `ensure_bucket()` creates the bucket if missing; safe to call repeatedly

Optional:
- `list_buckets() -> list[str]`
  - Lists bucket names accessible to the configured credentials

### 4.2 Core Object APIs (read/write/check/list/delete)

- `object_exists(object_name: str) -> bool`
  - Returns whether an object exists

- `get_bytes(object_name: str) -> bytes`
  - Reads an object as bytes

- `put_bytes(object_name: str, data: bytes, content_type="application/octet-stream") -> None`
  - Writes bytes

- `put_file(object_name: str, file_path, content_type: str | None = None) -> None`
  - Uploads a local file (suitable for large files like mp4/pptx/pdf)

- `get_file(object_name: str, file_path) -> None`
  - Downloads an object to a local file path (creates parent directories automatically)

- `get_json(object_name: str) -> Any`
- `put_json(object_name: str, payload: Any, ensure_ascii=False, indent=2) -> None`
  - JSON read/write (UTF-8)

- `list_object_names(prefix: str, recursive: bool = True) -> Iterator[str]`
  - Lists object keys (names) under a prefix

- `delete_object(object_name: str, bucket_name: str | None = None, missing_ok: bool = True) -> bool`
  - Deletes a single object; if `missing_ok=True`, missing objects are treated as non-errors

- `delete_prefix(prefix: str, bucket_name: str | None = None, recursive: bool = True) -> int`
  - Deletes all objects under a prefix (returns a best-effort count)

### 4.3 run_id Key Conventions: raw / derived

`MinioStore` provides recommended key conventions to organize artifacts from a single ingestion run under one prefix.

#### Raw object key

```python
raw_key = MinioStore.build_raw_object_key(run_id, asset_type, asset_id, filename)
```

Format:

```
runs/{run_id}/raw/{asset_type}/{asset_id}/{filename}
```

#### Derived object key

```python
derived_key = MinioStore.build_derived_object_key(run_id, asset_type, asset_id, relative_path)
```

Format:

```
runs/{run_id}/derived/{asset_type}/{asset_id}/{relative_path}
```

Recommended `relative_path` rules:
- Must be a relative path (do not start with `/`)
- Must not contain `..`
- The first segment should be a pipeline namespace (for example `frames-v1/`, `chunksum-v1/`) to avoid collisions

## 5) Running the Examples (examples/)

### 5.1 Example

```bash
cd <this-folder>
python examples/minio_api_example.py
```

Covers:
- `ensure_bucket()`
- `list_buckets()`
- `put_json/get_json`
- `put_bytes/get_bytes`
- `put_file/get_file`
- `object_exists/list_object_names`

Also covers:
- run_id-style keys: `build_raw_object_key()` / `build_derived_object_key()` 
- cleanup: `delete_object()` / `delete_prefix()`
