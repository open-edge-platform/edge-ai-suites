# 🎓 Smart Classroom
The Smart Classroom project is a modular, extensible framework designed to process and summarize educational content using advanced AI models. It supports transcription, summarization, and future capabilities like video understanding and real-time analysis. 

## This project provides: 

### 🔊 Audio file processing and transcription (e.g., Whisper, Paraformer) 
### 🧠 Summarization using powerful LLMs (e.g., Qwen, LLaMA) 
### 📦 Plug-and-play architecture for integrating new ASR and LLM models 
### ⚙️ API-first design ready for frontend integration 
### 🛠️ Ready-to-extend for real-time streaming, diarization, translation, and video analysis 
The goal is to transform raw classroom recordings into concise, structured summaries for students, educators, and learning platforms.

---
### 💻 System Requirements

- **OS:** Windows 11  
- **Processor:** Intel® Meteor Lake (with integrated GPU support)  
- **Memory:** 32 GB RAM (minimum recommended)  
- **Storage:** At least 50 GB free (for models and logs)  
- **GPU/Accelerator:** Intel® iGPU (Meteor Lake, Arc GPU, or higher) for summarization acceleration  
- **Python:** 3.12 or above  
- **Node.js:** v18+ (for frontend) 
---
### 🧩 Supported Models  

#### 🔊 ASR (Automatic Speech Recognition)  
- **Whisper (all models supported)**  
  - Recommended: `whisper-small` or lower for CPU efficiency  
  - Runs on **CPU** (Whisper is CPU-centric)  
- **FunASR (Paraformer)**  
  - Recommended for **Chinese transcription** (`paraformer-zh`)
- ✅ Supports transcription of audio files up to 45 minutes

#### 🧠 Summarization (LLMs)  
- **Qwen Models (OpenVINO / IPEX)**  
  - ✅ `Qwen2.0-7B-Instruct`  
  - ✅ `Qwen2.5-7B-Instruct`
- 💡 Summarization supports up to 7,500 tokens (≈ 45 minutes of audio) on GPU

#### ⚖️ Supported Weight Formats  
- **int8** → Recommended for lower-end CPUs (fast + efficient)  
- **fp16** → Recommended for higher-end systems (better accuracy, GPU acceleration)  
- **int4** → Supported, but may reduce accuracy (use only if memory-constrained)  

💡 Run summarization on **GPU** (Intel® iGPU / Arc GPU) for faster performance.  

---

### ✅ 1. **Install Dependencies**

**a. Install [FFmpeg](https://ffmpeg.org/download.html)** (required for audio processing):

* On **Windows**:
  Download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html), and add the `ffmpeg/bin` folder to your system `PATH`.

**b. Install Python dependencies:**

```bash
pip install --upgrade -r requirements.txt
```

**c. [Optional] Install IPEX-LLM to use IPEX-based LLM model for summarization:**

```bash
pip install --pre --upgrade ipex-llm[xpu_2.6] --extra-index-url https://download.pytorch.org/whl/xpu
```
---
### ⚙️ 2. Default Configuration

By default, the project uses Whisper for transcription and OpenVINO-based Qwen models for summarization.You can modify these settings in the configuration file:

```bash
asr:
  provider: openvino            # Supported: openvino, openai, funasr
  name: whisper-tiny          # Options: whisper-tiny, whisper-small, paraformer-zh etc.
  device: CPU                 # Whisper currently supports only CPU
  temperature: 0.0

summarizer:
  provider: openvino          # Options: openvino or ipex
  name: Qwen/Qwen2-7B-Instruct # Examples: Qwen/Qwen1.5-7B-Chat, Qwen/Qwen2-7B-Instruct, Qwen/Qwen2.5-7B-Instruct
  device: GPU                 # Options: GPU or CPU
  weight_format: int8         # Supported: fp16, fp32, int4, int8
  max_new_tokens: 1024        # Maximum tokens to generate in summaries
```
### 💡 Tips:
* For Chinese audio transcription, switch to funASR with Paraformer:

```bash
asr:
  provider: funasr
  name: paraformer-zh
```

* (Optional) If you want to use IPEX-based summarization, make sure IPEX-LLM is installed and set:

```bash
summarizer:
  provider: ipex
```

**Important: After updating the configuration, reload the application for changes to take effect.**

---

### ✅ 3. **Run the Application**

Bring Up Backend:
```bash
python main.py
```
**To monitor power usage, run your shell with admin privileges before starting the application.**

Bring Up Frontend:
```bash
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

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
