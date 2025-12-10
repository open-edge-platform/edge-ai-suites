# Get Started

This guide walks you through installing dependencies, configuring defaults, and running the application.

## Step 1: Install Dependencies

To install dependencies, do the following:

**a. Install [FFmpeg](https://ffmpeg.org/download.html)** (required for audio processing):

- Download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html), and add the `ffmpeg/bin` folder to your system `PATH`.

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
smartclassroom\Scripts\activate

# Use Python 3.12.x before running pip.
cd smart-classroom
python.exe -m pip install --upgrade pip
pip install --upgrade -r requirements.txt
```


**d. [Optional] Create Python Venv for Ipex Based Summarizer**
If you plan to use IPEX, create a separate virtual environment.


```bash
python -m venv smartclassroom_ipex
smartclassroom_ipex\Scripts\activate
# Use Python 3.12.x before running pip.
python.exe -m pip install --upgrade pip
cd smart-classroom
pip install --upgrade -r requirements.txt
pip install --pre --upgrade ipex-llm[xpu_2.6] --extra-index-url https://download.pytorch.org/whl/xpu
```
**Note: `smartclassroom_ipex` should only be used with FunAsr and Ipex related models (Specified in 2nd section). Don't configure Openvino related models in `smartclassroom_ipex`**
> 💡 *Use `smartclassroom` if you don’t need IPEX. Use `smartclassroom_ipex` if you want IPEX summarization.*

**e. Install DL Streamer**
Download the archive from [DL Streamer assets on GitHub](https://github.com/open-edge-platform/edge-ai-libraries/releases) Extract to a new folder, for example `C:\\dlstreamer_dlls`.

For details, refer to [Install Guide](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dl-streamer/get_started/install/install_guide_windows.html).

## Step 2: Configuration

### a. Default Configuration

By default, the project uses Whisper for transcription and OpenVINO-based Qwen models for summarization.You can modify these settings in the configuration file (`smart-classroom/config.yaml`):

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
### b. Chinese Audio Transcription

For Chinese audio transcription, switch to funASR with Paraformer in your config (`smart-classroom/config.yaml`):
```bash
asr:
  provider: funasr
  name: paraformer-zh
```

### c. IPEX-based Summarization

To use IPEX for summarization, ensure:
- IPEX-LLM is installed.
- The environment for IPEX is activated.
- The configuration (`smart-classroom/config.yaml`) is updated as shown below:

```bash
asr:
  provider: funasr
  name: paraformer-zh
summarizer:
  provider: ipex
```

**Important: After updating the configuration, reload the application for changes to take effect.**

## Step 3: Run the Application

Run setup script
Open a PowerShell prompt as and administrator, run the following script and follow instructions:
```
cd C:\\dlstreamer_dlls
.\setup_dls_env.ps1
```

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

> Open a second (new) Command Prompt / terminal window for the frontend. The backend terminal stays busy serving requests.

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

## Step 4: Access the UI

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

## Troubleshooting

- **Frontend not opening:**  
  Ensure you ran `npm run dev` in a second terminal after starting `python main.py`.

- **Backend not ready:**  
  Wait until Uvicorn shows **"Application startup complete"** and is listening on port **8000**.

- **URL fails from another device:**  
  Confirm you used `--host 0.0.0.0` and replaced `<HOST_IP>` correctly.

- **Nothing at http://localhost:5173:**  
  Check that the frontend terminal shows the Vite server running and no port conflict.

- **Firewall blocks access:**  
  Allow inbound traffic on ports **5173** (frontend) and **8000** (backend) on Windows.

- **Auto reload not happening:**  
  Refresh manually if the backend was restarted after initial UI load.

- **Error: `Port for tensor name cache_position was not found.`**  
  This means the models were not configured correctly.  
  To fix this:
  1. Delete the models directory:  
     ```
     edge-ai-suites/education-ai-suite/smart-classroom/models
     ```
  2. Rerun only Step 1’s option **c** (OpenVINO) or **d** (IPEX), whichever applies.

- **Tokenizer load issue:**  
  If you see this error:
    ``` bash
    Either openvino_tokenizer.xml was not provided or it was not loaded correctly. Tokenizer::encode is not available
    ```
  Delete the models folder from `edge-ai-suites/education-ai-suite/smart-classroom/models` and try again.

- If you see below error while running dls setup script,
    ``` bash
    .\setup_dls_env.ps1
      CategoryInfo          : SecurityError: (:) [], PSSecurityException
      FullyQualifiedErrorId : UnauthorizedAccess
    ```
  Run below command,
  ``` bash
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  ```

### Known Issues
 
- **Manual Video File Path Input**: Users are required to manually specify the path to video files from their local system in the base directory input. It is recommended to keep all video files in the same directory for seamless operation.
- **Live Video Monitoring Timeout**: Live video monitoring sessions will automatically stop after 45 minutes if the user does not reload the page to start a new session.
- **Stream End Notification**: Once the video streaming ends, the user will see a "Stream not found" message on the screen, indicating that the stream has concluded.
- **Do Not Reload During Active Streaming**: Users should not reload the page while the stream is active. Reloading the page will terminate the session, and the user will lose the current stream. Wait until the "Stream not found" notification appears on the screen before reloading.
- **Video Ready Notification**: If the URL is configured in the settings, the notification will display "Video Ready" unless the screen is reloaded. Reloading the screen will reset the session and the notification.

## Uninstall the Application

To uninstall the application, follow these steps:

1. **Delete the Python virtual environment folder:** \
   Navigate to the directory and remove \
   For base environment : *education-ai-suite/smartclassroom*. \
   For IPEX environemnt : *education-ai-suite/smartclassroom_ipex*.
2. **Remove the models directory:**
   Remove the models folder located under *education-ai-suite/smart-classroom*.
