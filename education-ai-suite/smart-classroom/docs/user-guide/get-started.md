# Quick Start Guide

> **Important:** Use **Windows PowerShell** (not Command Prompt/CMD) for all steps in this guide.
> PowerShell scripts (`.ps1` files) will not execute in CMD — they will only open as text files.

## Step 1: Clone Repository

Go to the target directory of your choice and clone the suite.
If you want to clone a specific release branch, replace `main` with the desired tag.
To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

```bash
  git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
  cd edge-ai-suites
  git sparse-checkout set education-ai-suite
  cd education-ai-suite\smart-classroom
```
## Step 2: Run Setup Script (First-Time Only)

```powershell
.\setup-smart-classroom.ps1
```

> **Note:** If all prerequisites are already installed (FFmpeg, DL Streamer, Python dependencies), you can skip setup and directly run `.\start-smart-classroom.ps1`.

The setup script will:

1. **[1] Check System Requirements**
   - OS version, CPU, RAM, storage
   - Python and Node.js versions

2. **[2] Application Dependency Check**
   - FFmpeg (auto-install if missing)
   - DL Streamer (auto-download and extract `dlstreamer_dlls_2026.0.0.zip` to `C:\dlls_windows`)

3. **[3] Configure Settings**
   - [3.1] Language & ASR Configuration (provider, model, device)
   - [3.2] Upload Size Limits
   - [3.3] OCR Configuration

4. **Launch Smart Classroom** (automatically runs `start-smart-classroom.ps1`)

## Step 3: Access the Application

Once all services are running, open your browser:

- **Local:** http://localhost:5173
- **Network:** http://YOUR_IP:5173

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

The startup script performs:

- **Service Detection** - Checks running services
- **Restart Options** - Restart, skip, or abort choices
- **Proxy Configuration** - Loads from `.proxy-config`
- **Sequential Launch** - Backend -> Content Search -> Frontend
- **Graceful Shutdown** - `Q` to stop all, `E` to keep running

---

## Manual Setup

 **[Advance Setup Guide](advance-setup-guide.md)**:  Follow step-by-step instructions to set up the application.

Advance Setup guide covers:

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
