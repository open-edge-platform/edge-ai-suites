# Windows startup scripts

This folder contains a one-key launcher for local Windows development:

- `run_all_service.ps1`: starts **MinIO + VLM + preprocess** in 3 separate PowerShell windows.

Related service scripts:

- `../content_search_minio/start_minio_server.ps1`
- `../vlm-openvino-serving/launch_service.ps1`
- `../video-chunk-summarization/launch_service.ps1`

---

## Quick start (one command)

Before first run:

1. Confirm [services_config.json](services_config.json) is configured.
2. Confirm [../content_search_minio/config.json](../content_search_minio/config.json) is configured.
3. Download MinIO executable (`minio.exe`) and set path in MinIO config if needed.

For MinIO setup details, use [../content_search_minio/README.md](../content_search_minio/README.md) as the single source of truth.

From repo root (`content-search`):

```powershell
powershell -NoProfile -ExecutionPolicy ByPass -File .\scripts\launch_all_services.ps1
```

What it does:

1. Launches MinIO service window
2. Launches VLM service window on `http://127.0.0.1:9900`
3. Launches preprocess service window on `http://127.0.0.1:8001`

You can also launch only specific services:

```powershell
powershell -NoProfile -ExecutionPolicy ByPass -File .\scripts\launch_all_services.ps1 -Services minio
powershell -NoProfile -ExecutionPolicy ByPass -File .\scripts\launch_all_services.ps1 -Services vlm
powershell -NoProfile -ExecutionPolicy ByPass -File .\scripts\launch_all_services.ps1 -Services preprocess
powershell -NoProfile -ExecutionPolicy ByPass -File .\scripts\launch_all_services.ps1 -Services minio,vlm
```

---

## Service config file

Default config file:

- `scripts/services_config.json`

The launcher reads this config by default. You can still override any value from CLI.

Preprocess defaults in config:
- `services.preprocess_chunk_duration_s`
- `services.preprocess_chunk_overlap_s`
- `services.preprocess_max_num_frames`
- `services.preprocess_frame_width`
- `services.preprocess_frame_height`

Set frame width/height to `0` to keep original video resolution.

```powershell
powershell -NoProfile -ExecutionPolicy ByPass -File .\scripts\launch_all_services.ps1 `
  -ModelName "Qwen/Qwen2.5-VL-3B-Instruct" `
  -Device GPU `
  -VlmPort 9900 `
  -PreprocessPort 8001
```

Example with custom config path:

```powershell
powershell -NoProfile -ExecutionPolicy ByPass -File .\scripts\launch_all_services.ps1 `
  -ConfigPath .\scripts\services_config.json
```

---

## Start each service directly (without launch_all_services.ps1)

From repo root:

```powershell
powershell -NoProfile -ExecutionPolicy ByPass -File .\content_search_minio\start_minio_server.ps1 -ConfigPath .\content_search_minio\config.json
```

```powershell
powershell -NoProfile -ExecutionPolicy ByPass -File .\vlm-openvino-serving\launch_service.ps1 -ModelName "Qwen/Qwen2.5-VL-3B-Instruct" -HostAddr 127.0.0.1 -Port 9900 -Device GPU -WeightFormat int8
```

```powershell
powershell -NoProfile -ExecutionPolicy ByPass -File .\video-chunk-summarization\launch_service.ps1 -HostAddr 127.0.0.1 -Port 8001 -VlmEndpoint "http://127.0.0.1:9900/v1/chat/completions" -VlmTimeoutSeconds 300
```

---

## Test Example:
1. Upload Video to MinIO:
python -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path('.').resolve())); from content_search_minio.minio_client import MinioStore; s=MinioStore.from_config(); s.ensure_bucket(); local=r'C:\path\to\store-aisle-detection.mp4'; key='runs/manual/raw/video/asset_001/store-aisle-detection.mp4'; s.put_file(key, local, content_type='video/mp4'); print('uploaded:', key)"

2. Prepare request to preprocess service:
PS C:\Users\user\Desktop\content-search> $req = @{
>>   minio_video_key = "runs/raw/video/asset_001/store-aisle-detection.mp4"
>>   chunk_duration_s = 30
>>   chunk_overlap_s = 4
>>   max_num_frames = 8
>>   prompt ="Please summarize this video"
>>   max_completion_tokens = 300
>> } | ConvertTo-Json -Depth 10
3. Send request to preprocess service:
PS C:\Users\user\Desktop\content-search> Invoke-RestMethod -Uri "http://127.0.0.1:8001/preprocess" -Method Post -ContentType "application/json" -Body $req
