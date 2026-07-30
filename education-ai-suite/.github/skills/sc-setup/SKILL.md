---
name: sc-setup
description: >
  Set up Flutter integration with the existing Content Search backend.
  Verifies Flutter SDK, installs Flutter dependencies, creates backend virtual
  environment, installs backend requirements, and runs utils/flutter/setup.ps1.
  Use when the user says "set up smart classroom", "run setup", "first time
  setup", "install dependencies", or "setup environment".
---

# SC Setup

Set up Flutter + Content Search backend integration with VLM service.
**Agent: execute every command below directly using your terminal tool and relay
the output.**

---

## What Gets Set Up

1. **Flutter dependencies** (via `flutter pub get`)
2. **Main backend venv** (`smartclassroom/`) — includes VLM service dependencies
3. **Content Search venv** (`venv_content_search/`) — RAG pipeline dependencies
4. **Flutter-specific configuration** — `utils/flutter/config.yaml` with only `content_search` and `qa` enabled

**Configuration approach:** Full config.yaml copy in `utils/flutter/` with all features disabled except `content_search` and `qa`. This prevents loading ASR, OCR, summarizer, and VA models.

**VLM Model:** Qwen3-VL-8B-Instruct (auto-downloaded on first run, shared by Content Search)

---

## Workflow

```powershell
.\utils\flutter\setup.ps1
```

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `flutter` command not found | Flutter SDK not in PATH | Install Flutter and add to PATH |
| `python` command not found | Python not installed | Install Python 3.12 and restart terminal |
| `pip install` fails | Network/proxy issue | Configure proxy and rerun setup |
| `setup.ps1` not found | Script missing in `utils/flutter/` | Add script or correct path before rerun |

---

## Output

Report: **Flutter detected** -> **pub dependencies installed** ->
**main backend venv ready (includes VLM)** -> **content search venv ready** -> **setup script finished**.
