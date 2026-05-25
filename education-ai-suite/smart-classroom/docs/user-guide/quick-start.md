# Quick Start Guide

The automated scripts handle dependency installation, basic configuration settings, and service startup with minimal user intervention.

### Step 1: Run Setup Script (First-Time Only)

Open PowerShell and navigate to the smart-classroom directory:

```powershell
cd edge-ai-suites\education-ai-suite\smart-classroom
.\setup-smart-classroom.ps1
```

> **Note:** If all prerequisites are already installed (FFmpeg, DL Streamer, Python dependencies), you can skip setup and directly run `.\start-smart-classroom.ps1`. Use this for subsequent runs or after modifying `config.yaml`.

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

### Step 2: Access the Application

Once all services are running, open your browser:

- **Local:** http://localhost:5173
- **Network:** http://\<YOUR_IP\>:5173

---

### Automated Setup - Troubleshooting

If you encounter issues during automated setup, refer to the manual steps below:

| Issue | Solution |
|-------|----------|
| FFmpeg installation fails | See [Manual Step 1A](#a-install-ffmpeg) |
| DL Streamer download fails | See [Manual Step 1B](#b-install-dl-streamer) |
| Python dependencies fail | See [Manual Step 1D](#d-install-python-dependencies) |
| Content Search fails | See [Manual Step 4](#step-4-set-up-content-search) |
| Frontend fails to start | See [Manual Step 5](#step-5-bring-up-the-frontend) |
| Proxy/network issues | Configure proxy in setup script or see [Network Requirements](#c-network-requirements-for-content-search) |

---

## Starting Smart Classroom

After initial setup is complete, use the start script for subsequent runs or after modifying `config.yaml`:

```powershell
.\start-smart-classroom.ps1
```

> **Tip:** If you modify `config.yaml`, just run this script directly — no need to re-run `setup-smart-classroom.ps1`.

> **For more details on individual components, troubleshooting, or custom configurations, refer to the [Manual Setup](#manual-setup) section below.**

---

## Manual Setup

For full control, custom configurations, or troubleshooting:

**[Get Started - Manual Installation Guide](get-started.md)**

The manual guide covers:

- **Step 1:** Install Dependencies (FFmpeg, DL Streamer, Python, Content Search)
- **Step 2:** Configuration (config.yaml settings)
- **Step 3-6:** Run Services & Access UI
- **Step 7:** Speaker Diarization Setup (Optional)

---

## Service Ports Reference

| Service | Port | Health Check |
|---------|------|--------------|
| Backend | 8000 | http://localhost:8000/health |
| Content Search | 9011 | http://localhost:9011/api/v1/system/health |
| Frontend | 5173 | http://localhost:5173 |


