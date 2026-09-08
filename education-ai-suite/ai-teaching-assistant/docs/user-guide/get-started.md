# Get Started

Set up the AI Teaching Assistant on Windows and ingest your first course materials.

Confirm your machine meets the [System Requirements](./get-started/system-requirements.md) before starting.

> **Important:** Use **Windows PowerShell** (not Command Prompt/CMD) for all steps in this guide.
> PowerShell scripts (`.ps1` files) will not execute in CMD — they will only open as text files.

## Step 1: Prerequisites

- **Git for Windows** — [Download here](https://git-scm.com/download/win)
- **Python 3.11 or 3.12** — [Download here](https://www.python.org/downloads/) (check "Add Python to PATH")
- **Visual C++ Build Tools** — Required for some Python packages

## Step 2: Clone The Repository

Open PowerShell and run:

```powershell
git clone --filter=blob:none --sparse https://github.com/open-edge-platform/edge-ai-suites.git -b main `
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

```text
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

## Uninstall

The application has no installer — all files live inside the cloned repository. To uninstall, stop the services and delete the Python virtual environments (`venv`) along with the downloaded models, storage, and cache folders.

> **Warning:** Deleting the `storage/` folders permanently removes user data, including the RAG vector database of your ingested course materials (`rag-service/storage/vector_db`). Back up anything you want to keep first.

1. Stop all services:

   ```powershell
   .\stop_ata.ps1
   ```

2. Run the uninstall script from the `ai-teaching-assistant` directory:

   ```powershell
   .\uninstall_ata.ps1
   ```

   The script lists the folders it will delete and asks for confirmation before removing the `venv`, `models`, `storage`, and `.cache` folders for every service.

   Options:

   ```powershell
   # Skip the confirmation prompt
   .\uninstall_ata.ps1 -Yes

   # Also delete the Hugging Face cache in your user profile
   .\uninstall_ata.ps1 -Yes -RemoveHfCache
   ```

3. (Optional) To remove the entire application, delete the cloned repository folder.

To reinstall later, re-run `.\setup_windows.ps1` — it will recreate the virtual environments and re-download the models. Ingested course materials will need to be uploaded again.

> **Note:** If you deleted the cloned repository folder in step 3, re-run [Step 2: Clone The Repository](#step-2-clone-the-repository) first — `setup_windows.ps1` lives inside the repo, so running it alone is not enough.

## Next Steps

- [Application Flow](./application-flow.md) — UI walkthrough and element reference
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
