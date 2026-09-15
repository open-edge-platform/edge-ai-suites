---
name: sc-up
description: >
  Bring up the Flutter implementation with the existing Content Search backend.
  Runs the startup script at utils/flutter/start.ps1 and validates
  application health.
  Use when the user says "start smart classroom", "run the app", "launch smart
  classroom", "bring up services", or "open smart classroom".
---

# SC Up

Start the Flutter implementation with Content Search backend and VLM service.
**Agent: execute every command below directly using your terminal tool and relay
the output.**

---

## What Starts

1. **Main backend** (port 8000) — Single process using Flutter's config.yaml
   - Loads ONLY VLM service (Qwen3-VL-8B-Instruct)
   - ASR, OCR, summarizer models NOT loaded (features disabled in Flutter config)
   - **Initial startup takes 2-3 minutes** for VLM model loading
   - Config: `utils/flutter/config.yaml` (passed via `SC_CONFIG_PATH` environment variable)
2. **Content Search** (port 9011) — auto-started by main backend as subprocess
   - Inherits `SC_CONFIG_PATH` from parent process
   - Uses same Flutter config for consistent settings
   - Starts ChromaDB, file ingest, and Q&A services
3. **Flutter app** — Windows application for RAG interactions

**Architecture:** Flutter → Content Search (RAG) → VLM (answer generation)

**Key optimization:** Both main backend and Content Search use `utils/flutter/config.yaml` via `SC_CONFIG_PATH`, ensuring all features disabled except `content_search` and `qa`, preventing unnecessary model loading.

---

## Workflow

### 1. Run startup script

```powershell
.\utils\flutter\start.ps1
```

**Note:** The startup script already includes backend health verification. No additional health check is needed.

**Startup timing:** Wait 2-3 minutes for VLM model to load before the Flutter app launches.

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `start.ps1` not found | Script missing in `utils/flutter/` | Add script or correct path |
| Health endpoint unreachable | Backend not started by script | Run `sc-setup`, then rerun `sc-up` |
| VLM service takes too long | Model downloading/loading | Normal on first run; wait 2-3 minutes |
| Content Search fails to start | VLM not ready | Check main backend logs; VLM must be healthy first |

---

## Output

Report: **main backend starting (VLM loading)** -> **content search auto-started** -> **services healthy** -> **Flutter app launched**.
