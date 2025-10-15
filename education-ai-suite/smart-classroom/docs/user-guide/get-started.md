# Get Started

This guide walks you through installing dependencies, configuring defaults, and running the application.

## Step 1: Install Dependencies

To install dependencies, do the following:

**a. Install [FFmpeg](https://ffmpeg.org/download.html)** (required for audio processing):

- On **Windows**:  
  Download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html), and add the `ffmpeg/bin` folder to your system `PATH`.

**Run your shell with admin privileges before starting the application**

**b. Clone Repository:**

```bash
  git clone --no-checkout https://github.com/open-edge-platform/edge-ai-suites.git
  cd edge-ai-suites
  git sparse-checkout init --cone
  git sparse-checkout set education-ai-suite
  git checkout
  cd education-ai-suite
```

**c. Install Python dependencies**

It’s recommended to create a **dedicated Python virtual environment** for the base dependencies.

```bash
python -m venv smartclassroom
# On Windows:
smartclassroom\Scripts\activate

python.exe -m pip install --upgrade pip
pip install --pre --upgrade ipex-llm[xpu_2.6] --extra-index-url https://download.pytorch.org/whl/xpu
pip install --upgrade -r requirements.txt
```


**d. [Optional] Create Python Venv for Ipex Based Summarizer**  
If you plan to use IPEX, create a separate virtual environment.

```bash
python -m venv smartclassroom_ipex
# On Windows:
smartclassroom_ipex\Scripts\activate

python.exe -m pip install --upgrade pip
pip install --upgrade -r requirements.txt
pip install --pre --upgrade ipex-llm[xpu_2.6] --extra-index-url https://download.pytorch.org/whl/xpu
```
> 💡 *Use `smartclassroom` if you don’t need IPEX. Use `smartclassroom_ipex` if you want IPEX summarization.*

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
### 💡 Tips:
* For Chinese audio transcription, switch to funASR with Paraformer:

```bash
asr:
  provider: funasr
  name: paraformer-zh
```

* (Optional) If you are using IPEX-based summarization, make sure IPEX-LLM is installed, env for ipex is activated and set following in `config`:

```bash
summarizer:
  provider: ipex
```

**Important: After updating the configuration, reload the application for changes to take effect.**

## Step 3: Run the Application

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

## Check Logs

Once the backend starts, you can see the following logs:

```bash
pipeline initialized
[INFO] __main__: App started, Starting Server...
INFO:     Started server process [21616]
	@@ -92,5 +166,6 @@ INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

This means your pipeline server is up and ready to accept requests.
