# System Requirements

## Windows OS

- **Windows 10** — Build 19041 or later
- **Windows 11** — All builds supported
- **Windows Server 2022** — Not recommended for interactive use

PowerShell 5.1+ (included with Windows 10/11).

## Hardware

### Processor
- **Recommended** — Intel Core i7 or i9 (10th generation or newer)
  - 8-16 cores ideally
  - Examples: i7-10700, i9-12900, Core Ultra (Meteor Lake)
- **Minimum** — Intel Core i5 (8th generation or newer)
- **GPU** (optional) — Intel integrated GPU (Iris Xe or newer) or discrete GPU
  - Accelerates LLM inference by 2-4x
  - Not required for baseline functionality

### Memory
- **Minimum** — 16 GB RAM
- **Recommended** — 32 GB RAM
- **Optimal** — 64 GB RAM (headroom for models plus browser and OS)

The default LLM is `Qwen/Qwen3-4B-Instruct-2507` (int8) configured in
`rag-service/config.yaml`. With less than 16 GB RAM, switch to a smaller
Qwen instruct model in that config for smoother performance.

### Storage
- **Minimum** — 50 GB free SSD space
  - ~30-40 GB for LLM + embedding + TTS models
  - ~5-10 GB for Chroma vector database (scales with documents)
  - ~5 GB for system and cache
- **Recommended** — 100 GB+ free space (NVMe SSD preferred)

HDD is **not recommended** — model loading and inference will be slow.

### Microphone
- **Required for voice input** — The assistant captures your speech through the browser, so a working microphone is needed for mic-based interaction.
- **Optional for text-only usage** — If you use typed input and do not use voice features, a microphone is not required.
If multiple microphones are available, choose the input device from the UI microphone selector.

## Software Dependencies

### Python
- **Python 3.11** or **3.12** 
- Download from [python.org](https://www.python.org/downloads/)
- During installation, **check "Add Python to PATH"**

### Git for Windows
- [Download from git-scm.com](https://git-scm.com/download/win)
- Use default installation settings

### Visual C++ Build Tools
- Required for building Python packages (e.g., `cryptography`)
- [Download from Microsoft](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
- Or install Visual Studio Community with C++ workload

## Network

- **Outbound internet** — Required on first run to download:
  - AI models from Hugging Face (~30-50 GB)
  - Python packages from PyPI
- **Localhost ports** — Services bind to:
  - `7860` — ai-teaching-assistant ui (browser interface)
  - `8010` — audio-analyzer (speech-to-text)
  - `8011` — text-to-speech
  - `8012` — kiosk-core (orchestrator)
  - `8020` — rag-service (knowledge base & LLM)
- **Firewall** — Windows Defender Firewall may prompt; allow when running

## Browser Requirements

Any modern browser:
- **Microsoft Edge** ✓ (recommended)
- **Google Chrome** ✓
- **Mozilla Firefox** ✓
- **Safari** ✓

Must have:
- JavaScript enabled
- WebAudio API support (for microphone capture)
- Cookies enabled
- Ability to access `http://127.0.0.1:7860`

**Microphone permission** — When you first open the interface, your browser will request microphone access. Click "Allow".

## Performance Tips

### For Faster Inference
1. **Use a smaller Qwen instruct model** than the default `Qwen3-4B-Instruct`
2. **Enable GPU acceleration** if you have an Intel GPU (Iris Xe or newer)
3. **Increase system RAM** to avoid disk swapping
4. **Use NVMe SSD** for model storage

### For Better Answers
1. **Use a larger Qwen instruct model** than the default `Qwen3-4B-Instruct`
2. **Upload more course materials** to the knowledge base
3. **Enable reranking** in configuration (improves answer relevance)
4. **Adjust top-K** — Retrieve more chunks for complex topics

### For Multi-User Deployment
- Ensure machine has 64+ GB RAM
- Use a modern i9 CPU
- Consider running only `rag-service` on one machine and `audio-analyzer` + `text-to-speech` on another (advanced)

## Verification

Before running the application, verify your setup:

```powershell
# Check Windows version
[System.Environment]::OSVersion.Version

# Check Python installation
python --version

# Check Git installation
git --version

# Verify network connectivity
curl https://www.google.com
```

All commands should succeed.

## Troubleshooting Prerequisites

| Issue | Solution |
|-------|----------|
| "Python not found" | Add Python to PATH: Go to Settings > Environment Variables and add Python install directory |
| "Port already in use" | Find and stop process by PID: `netstat -ano | findstr :7860` then `taskkill /PID <pid> /F` |
| "Insufficient disk space" | Use an external SSD or upgrade storage |
| "Out of memory" | Close other applications or upgrade RAM |
| "Slow inference" | Disable background tasks (Windows Update, antivirus scans) during use |

See [Troubleshooting](../troubleshooting.md) for more issues.

