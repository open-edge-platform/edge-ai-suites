# Run Services Manually on Windows

Use this guide when you want to run services individually for debugging or
custom development. For normal usage, prefer `start_ata.ps1`.

## Scope

This is a Windows-native workflow.

## Prerequisite

Clone and enter the application directory as shown in
[Get Started](../get-started.md), then run:

```powershell
.\setup_windows.ps1
```

`setup_windows.ps1` prepares required submodules, virtual environments, and dependencies.

## Service Startup Order

Start each service in a dedicated PowerShell terminal.

### 1) metrics-collector (Port 9000)

```powershell
cd metrics_collector\windows
.\metrics_collector.ps1
```

Health check:
```powershell
curl http://127.0.0.1:9000/health
```

### 2) text-to-speech (Port 8011)

```powershell
cd edge-ai-libraries\microservices\text-to-speech
.\venv\Scripts\python.exe main.py
```

Health check:
```powershell
curl http://127.0.0.1:8011/health
```

### 3) audio-analyzer (Port 8010)

```powershell
cd edge-ai-libraries\microservices\audio-analyzer
.\venv\Scripts\python.exe main.py
```

Health check:
```powershell
curl http://127.0.0.1:8010/health
```

### 4) rag-service (Port 8020)

```powershell
cd voice-enabled-interactions\smart-kiosk-assistant\rag-service
.\venv\Scripts\python.exe main.py
```

Health check:
```powershell
curl http://127.0.0.1:8020/health
```

### 5) kiosk-core (Port 8012)

```powershell
cd voice-enabled-interactions\smart-kiosk-assistant
.\venv\Scripts\python.exe main.py
```

Health check:
```powershell
curl http://127.0.0.1:8012/health
```

### 6) ai-teaching-assistant ui proxy server (Port 7860)

```powershell
cd .
voice-enabled-interactions\smart-kiosk-assistant\venv\Scripts\python.exe ata_ui_server.py
```

Health check:
```powershell
curl http://127.0.0.1:7860/healthz
```

Open:
```text
http://127.0.0.1:7860
```

## Build React UI (if needed)

If `ata_ui_server.py` reports that React assets are missing:

```powershell
cd assistant-react-ui
npm install
npm run build
```

Then restart `ata_ui_server.py`.

## Verify End-to-End

1. Upload one or more documents in the Knowledge Base panel.
2. Click mic, ask a question.
3. Confirm transcript, answer text, and spoken response.

## Stop Services

Press `Ctrl+C` in each terminal.

Or use:

```powershell
.\stop_ata.ps1
```

## Notes

- The launcher flow (`start_ata.ps1`) is the supported default.
- Manual mode is primarily for debugging service-level behavior.
- Response audio clips are written under `generated_audio/` in the kiosk-core area.
