# Get Started with Smart Classroom

> **Important:** Use **Windows PowerShell** (not Command Prompt/CMD) for all steps in this guide.
> PowerShell scripts (`.ps1` files) will not execute in CMD — they will only open as text files.

## Step 1: Clone the Repository

Go to the target directory of your choice and clone the suite.
If you want to clone a specific release branch, replace `main` with the desired tag.
To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

```bash
  git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
  cd edge-ai-suites
  git sparse-checkout set education-ai-suite
  cd education-ai-suite\smart-classroom
```
## Step 2: Run the Setup Script (First-Time Only)

```powershell
.\setup-smart-classroom.ps1
```

> **Note:** If all prerequisites are already installed (FFmpeg, DL Streamer, Python
> dependencies), you can skip setup and directly run `.\start-smart-classroom.ps1`.

The setup script will:

1. **[1] Check System Requirements**
   - OS version, CPU, RAM, storage
   - Python and Node.js versions

2. **[2] Application Dependency Check**
   - FFmpeg (auto-install if missing)
   - DL Streamer (auto-download and run installer [`dlstreamer-2026.1.0-win64.exe`](advance-setup-guide.md#b-install-dl-streamer))

3. **[3] Configure Settings**
   - [3.1] Language & ASR Configuration (provider, model, device)
   - [3.2] Upload Size Limits
   - [3.3] OCR Configuration

4. **Complete Setup** (to start services, run `start-smart-classroom.ps1` separately)

## Step 3: Access the Application

Once all services are running, open your browser:

- **Local:** http://localhost:5173
- **Network:** http://YOUR_IP:5173

> **Prefer a desktop app?** Start the script with `.\start-smart-classroom.ps1 -Electron`
> to open the UI in an Electron desktop window instead of a browser tab. See
> [Optional Parameters](#starting-smart-classroom) below.

---

## Automated Setup - Troubleshooting

If you encounter issues during automated setup, refer to the manual steps below:

| Issue | Solution |
|-------|----------|
| `PSSecurityException` when running `.ps1` scripts | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in PowerShell |
| FFmpeg installation fails | See [Manual Step 1A](advance-setup-guide.md#a-install-ffmpeg-required-for-audio-processing) |
| DL Streamer download fails | See [Manual Step 1B](advance-setup-guide.md#b-install-dl-streamer) |
| Python dependencies fail | See [Manual Step 1D](advance-setup-guide.md#d-install-python-dependencies) |
| Content Search fails | See [Manual Step 4](advance-setup-guide.md#step-4-set-up-content-search) |
| Frontend fails to start | See [Manual Step 5](advance-setup-guide.md#step-5-bring-up-the-frontend) |

---

## Starting Smart Classroom

After initial setup is complete, use the start script for subsequent runs or after modifying `config.yaml`:

```powershell
.\start-smart-classroom.ps1
```

**Optional Parameters:**
- `-Electron` - Launch the UI as an Electron desktop app instead of a browser tab (the UI dev server still runs on port 5173)
- `-Silent` - Unattended mode for CI/Ansible (skips all prompts, auto-restarts services)
- `-NoElevate` - Skip admin privilege elevation (use when already running as administrator)
- `-NoWindowsTerminal` - Use Invoke-WmiMethod instead of Windows Terminal (for remote sessions/Ansible)

```powershell
# Example: Launch the UI as a desktop app
.\start-smart-classroom.ps1 -Electron

# Example: Automated deployment
.\start-smart-classroom.ps1 -Silent -NoElevate -NoWindowsTerminal
```

The startup script performs:

- **Service Detection** - Checks running services
- **Restart Options** - Restart, skip, or abort choices (auto in `-Silent` mode)
- **Proxy Configuration** - Loads from `.proxy-config`
- **Sequential Launch** - Backend -> Content Search -> Frontend
- **Graceful Shutdown** - `Q` to stop all, `E` to keep running (auto-exits in `-Silent` mode)

---

## Manual Setup

**[Advanced Setup Guide](advance-setup-guide.md)**:  Follow step-by-step instructions to set up the application.

Advanced Setup guide covers:

- **Step 1:** Install Dependencies (FFmpeg, DL Streamer, Python, Content Search)
- **Step 2:** Configuration (config.yaml settings)
- **Step 3-6:** Run Services & Access UI
- **Step 7:** Speaker Diarization Setup (Optional)
- **[Troubleshooting](advance-setup-guide.md#troubleshooting)** — solutions for common setup and runtime issues
- **[Known Issues](advance-setup-guide.md#known-issues)** — current limitations and workarounds
- **[Uninstall the Application](advance-setup-guide.md#uninstall-the-application)** — steps to cleanly remove the environment and models

---

## Service Ports Reference

| Service | Port | Health Check |
|---------|------|--------------|
| Backend | 8000 | http://localhost:8000/health |
| Content Search | 9011 | http://localhost:9011/api/v1/system/health |
| Frontend | 5173 | http://localhost:5173 |

## Learn More

- [System Requirements](./get-started/system-requirements.md): Hardware, software, supported models, and weight formats.
- [Application Flow](./application-flow.md): End-to-end application flow.
- [Content Search Flow](./content-search-flow.md): The flow of the content search functionality.
