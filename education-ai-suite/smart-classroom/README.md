# 🎓 Smart Classroom

The **Smart Classroom** project is a modular, extensible framework designed to process and summarize educational content using advanced AI models. It supports transcription, summarization, and future capabilities like video understanding and real-time analysis. 

The main features are as follows:

•	Audio transcription with ASR models (e.g., Whisper, Paraformer)
•	Summarization using powerful LLMs (e.g., Qwen, LLaMA)
•	Plug-and-play architecture for integrating new ASR and LLM models
•	API-first design ready for frontend integration
•	Extensible roadmap for real-time streaming, diarization, translation, and video analysis


## Get Started 

To see the system requirements and other installations, see the following guides:

- [System Requirements](./docs/user-guide/system-requirements.md): Check the hardware and software requirements for deploying the application.
- [Get Started](./docs/user-guide/get-started.md): Follow step-by-step instructions to set up the application.

## How It Works

The basic architecture follows a modular pipeline designed for efficient audio summarisation. It begins with **audio preprocessing**, where FFMPEG chunks input audio into smaller segments for optimal handling. These segments are processed by an **ASR transcriber** (e.g., Whisper or Paraformer) to convert speech into text. Finally, an **LLM summariser** (such as Qwen or Llama), optimised through frameworks like OpenVINO IR, Llama.cpp, or IPEX, generates concise summaries, which are delivered via the **output handler** for downstream use.

![High-Level System Diagram](./docs/user-guide/images/architecture.svg)

## Learn More

```bash
asr:
  provider: funasr
  name: paraformer-zh
```

* (Optional) If you want to use IPEX-based summarization, make sure IPEX-LLM is installed, env for ipex is activated and set following in `config`:

```bash
summarizer:
  provider: ipex
```

**Important: After updating the configuration, reload the application for changes to take effect.**

---

### ✅ 3. **Run the Application**
Activate the environment before running the application:

```bash
smartclassroom\Scripts\activate  # or smartclassroom_ipex
```
Run the backend:
```bash
python main.py
```

- Bring Up Frontend:
```bash
cd ui
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

> ℹ️ Open a second (new) Command Prompt / terminal window for the frontend. The backend terminal stays busy serving requests.

💡 Tips: You should see backend logs similar to this:

```
pipeline initialized
[INFO] __main__: App started, Starting Server...
INFO:     Started server process [21616]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

This means your pipeline server has started successfully and is ready to accept requests.

---

### 🖥️ 4. Access the UI

After starting the frontend you can open the Smart Classroom UI in a browser:

Local machine:
- http://localhost:5173
- http://127.0.0.1:5173

From another device on the same network (replace <HOST_IP> with your computer’s IP):
- http://<HOST_IP>:5173

Find your IP (Windows PowerShell):
```
ipconfig
```
Use the IPv4 Address from your active network adapter.

If you changed the port, adjust the URL accordingly.

---

### 🔍 6. Troubleshooting (Focused)

- Frontend not opening: Ensure you ran npm run dev in a second terminal after starting python main.py.
- Backend not ready: Wait until Uvicorn shows "Application startup complete" and listening on port 8000.
- URL fails from another device: Confirm you used --host 0.0.0.0 and replace <HOST_IP> correctly.
- Nothing at localhost:5173: Check that the frontend terminal shows Vite server running and no port conflict.
- Firewall blocks access: Allow inbound on ports 5173 (frontend) and 8000 (backend) on Windows.
- Auto reload not happening: Refresh manually if backend was restarted after initial UI load.


•	[Release Notes](./docs/user-guide/release-notes.md)
