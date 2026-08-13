# Get Started

Set up the AI Teaching Assistant on Windows and ingest your first course materials.

Confirm your machine meets the [System Requirements](./get-started/system-requirements.md) before starting.

## Step 1: Prerequisites

- **Git for Windows** — [Download here](https://git-scm.com/download/win)
- **Python 3.10+** — [Download here](https://www.python.org/downloads/) (check "Add Python to PATH")
- **Visual C++ Build Tools** — Required for some Python packages

## Step 2: Clone The Repository

Open PowerShell and run:

```powershell
git clone --filter=blob:none --sparse https://github.com/open-edge-platform/edge-ai-suites.git `
; cd edge-ai-suites `
; git sparse-checkout set education-ai-suite/ai-teaching-assistant `
; cd education-ai-suite/ai-teaching-assistant
```

## Step 3: Run Windows Setup

PowerShell script handles all setup (Python venv, dependencies, models):

```powershell
# If prompted about execution policy, run:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

.\setup_windows.ps1
```

Note: This setup script also initializes the required submodules automatically.

The script will:
1. Create and activate a Python virtual environment
2. Download and install model files (~30-50 GB)
3. Install all dependencies for the five services

**First run may take 10-30 minutes** while models are downloaded and cached.

## Step 4: Start the Application

```powershell
.\start_ata.ps1
```

Services will start in sequence:
- `audio-analyzer` (8010)
- `text-to-speech` (8011)
- `rag-service` (8020)
- `kiosk-core` (8012)
- `ai-teaching-assistant ui` (7860)

Wait for all services to show "ready" in the terminal.

## Step 5: Verify All Services Are Running

Open PowerShell and verify health:

```powershell
# Audio-to-text
curl http://127.0.0.1:8010/health

# Text-to-speech
curl http://127.0.0.1:8011/health

# RAG service
curl http://127.0.0.1:8020/health

# Session orchestrator
curl http://127.0.0.1:8012/health
```

Each response should be: `{"status": "ok"}`

## Step 6: Access the Web Interface

Open your browser and navigate to:

```
http://127.0.0.1:7860
```

You should see the AI Teaching Assistant interface.

## Step 7: Ingest Course Materials

1. In the browser, go to the **"Knowledge Base"** panel
2. Click **"Choose Files"** and select your course material (`.txt`, `.md`, `.docx`, or `.pdf`)
3. Click **"Upload"** — wait for "Upload successful" confirmation


## Stopping the Application

```powershell
.\stop_ata.ps1
```

To stop individual services, use `Ctrl+C` in their respective terminal windows.

## Next Steps

- [How It Works](./how-it-works.md) — Understand the architecture
- [Configuration](./get-started/configuration.md) — Adjust models, temperature, and settings
- [Troubleshooting](./troubleshooting.md) — Debug common issues
- [API Reference](./api-reference.md) — Integrate with external apps

<!--hide_directive
:::{toctree}
:hidden:

./get-started/system-requirements.md
./get-started/run-standalone.md
./get-started/configuration.md

:::
hide_directive-->
