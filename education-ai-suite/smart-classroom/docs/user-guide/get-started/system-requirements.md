# System Requirements

This page provides detailed hardware, software, platform requirements, and supported models to help you set up and run the application efficiently.

## Software and Hardware Requirements

- **OS**: Windows 11
- **Recommended processor**: Intel® Core Ultra Series 1, 2, and 3 Processors (with integrated GPU support)
- **Memory**: 32 GB RAM (minimum recommended)
- **Storage**: At least 50 GB free (for models and logs)
- **GPU/Accelerator**: Intel® iGPU (Core Ultra Series 1, Arc GPU, or higher) for summarization acceleration
- **NPU**: Intel® NPU (Core Ultra Series 1 or higher) for Video pipelines
- **NPU Driver**: Please download and install the latest version from [Intel NPU Driver Download Page](https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html)
- **Python**: 3.12
- **Node.js**: v18+ (for frontend)

## Audio Pipeline Supported Models  

### ASR (Automatic Speech Recognition)  

- **Whisper (all models supported)**  
  - Recommended: `whisper-small` or lower for CPU efficiency  
  - Runs on **CPU** (Whisper is CPU-centric)  
- **FunASR (Paraformer)**  
  - Recommended for **Chinese transcription** (`paraformer-zh`)
-  Supports transcription of .mp3/.wav audio files up to 45 minutes long.

###  Summarization (LLMs)  
- **Qwen Models (OpenVINO / IPEX)**  
  - `Qwen2.0-7B-Instruct`  
  -  `Qwen2.5-7B-Instruct`
-  Summarization supports up to 7,500 tokens (≈ 45 minutes of audio) on GPU
-  Run summarization on **GPU** (Intel® iGPU / Arc GPU) for faster performance.

### Content Segmentation and Topic Search

- **Embedding Model**: `BAAI/bge-large-en-v1.5` for semantic topic indexing and search
- **Vector Store**: FAISS (IndexFlatIP with cosine similarity)
- Content segmentation uses the same LLM as summarization (e.g., Qwen2.5-7B-Instruct)

###  Supported Weight Formats  
- **int8** → Recommended for lower-end CPUs (fast + efficient)  
- **fp16** → Recommended for higher-end systems (better accuracy, GPU acceleration)  
- **int4** → Supported, but may reduce accuracy (use only if memory-constrained)  

## Video Analytics Pipeline

- Supports 3 concurrent video pipelines (front, back, content) up to 45 minutes
- Supports .mp4 format and RTSP streams
- Outputs processed video via RTSP and HLS streaming (MediaMTX)

For pipeline architecture and processing stages, see [How It Works](../how-it-works.md#video-analytics-pipeline).

### Supported Models

| Model | Format | Used In | Purpose |
| ----- | ------ | ------- | ------- |
| **YOLOv8m-pose** | OpenVINO IR | Front pipeline | Person detection + 17-keypoint pose estimation |
| **YOLOv8s-pose** | OpenVINO IR | Back pipeline | Lightweight person detection + pose estimation |
| **ResNet-18** | OpenVINO IR | Front, Back, Content | Activity/action classification |
| **MobileNet-V2** | OpenVINO IR | Front pipeline | Lightweight classification |
| **Person-ReID-retail-0288** | OpenVINO IR | Front pipeline | Person re-identification and tracking |

- All models run in OpenVINO Intermediate Representation (IR) format
- Inference supported on **CPU**, **GPU**, and **NPU** (configurable per pipeline)
- Default inference device: **NPU** (recommended for best performance on Intel® Core Ultra)
