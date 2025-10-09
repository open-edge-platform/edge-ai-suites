# Get Started

This guide walks you through installing dependencies, configuring defaults, and running the application.


## Step 1: Install Dependencies

To install dependencies, do the following:

1. Install FFmpeg (Required for Audio Processing)

Windows: Download from https://ffmpeg.org/download.html
After installation, add the ffmpeg/bin folder to your system PATH

2. Install Python Packages

```bash
pip install --upgrade -r requirements.txt
```

3. [Optional] Install IPEX-LLM for IPEX-based summarization

```bash
pip install --pre --upgrade ipex-llm[xpu_2.6] --extra-index-url https://download.pytorch.org/whl/xpu
```

## Step 2: Configure Defaults

The default setup uses Whisper for transcription and OpenVINO Qwen models for summarization. You can customize these in the configuration file.

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

💡 Tips:

For Chinese transcription, switch to FunASR with Paraformer:

```bash
asr:
  provider: funasr
  name: paraformer-zh
```

If you are using IPEX summarization, ensure ipex-llm is installed and update:

```bash
summarizer:
  provider: ipex
```

Note: After updating the configuration, reload the application for changes to take effect.


## Step 3: Run the Application

Bring up Backend:

```bash
python main.py
```

Bring up Frontend:

```bash
cd ui
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## Check Logs

Once the backend starts, you can see the following logs:

```bash
pipeline initialized
[INFO] __main__: App started, Starting Server...
INFO:     Started server process [21616]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

This means your pipeline server is up and ready to accept requests.

