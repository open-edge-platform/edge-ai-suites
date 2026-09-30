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
- Supports transcription of .mp3/.wav audio files up to 45 minutes long.

### Summarization (LLMs)

- **Qwen Models (OpenVINO™)**
  - `Qwen3-VL-8B-Instruct` (default, shared vision-language model)
  - `Qwen3.5-9B`
- Summarization supports up to 5,120 tokens on GPU
- Run summarization on **GPU** (Intel® iGPU / Arc GPU) for faster performance.

### Content Segmentation and Topic Search

- **Embedding Model**: `intfloat/multilingual-e5-small` for semantic topic indexing and search
- **Vector Store**: ChromaDB
- **Content segmentation**: uses the shared vision-language model (`Qwen3-VL-8B-Instruct` by default)

### Supported Weight Formats

- **int4** → Recommended default (fast + memory-efficient on GPU)
- **int8** → Higher accuracy, larger memory footprint
- **fp16** → Full precision (use only if sufficient memory available)

## Video Analytics Pipeline

- Supports 3 concurrent video pipelines (front, back, content) up to 45 minutes
- Supports .mp4 format and RTSP streams
- Outputs processed video via RTSP and HLS/WebRTC streaming (MediaMTX)

For pipeline architecture and processing stages, see [How It Works](../how-it-works.md#video-analytics-pipeline).

### Supported Models

| Model | Format | Used In | Purpose |
| ----- | ------ | ------- | ------- |
| **YOLOv8m-pose** (default) | OpenVINO™ IR | Front pipeline | Person detection + 17-keypoint pose estimation |
| **YOLOv8s-pose** (default) | OpenVINO™ IR | Back pipeline | Lightweight person detection + pose estimation |
| **YOLO11m/s-pose** | OpenVINO™ IR | Front / Back pipeline | Alternative pose model |
| **YOLO26m/s-pose** | OpenVINO™ IR | Front / Back pipeline | Alternative pose model |
| **ResNet-18** | OpenVINO™ IR | Front, Back, Content | Activity/action classification |
| **MobileNet-V2** | OpenVINO™ IR | Front pipeline | Lightweight classification |
| **Person-ReID-retail-0288** | OpenVINO™ IR | Front pipeline | Person re-identification and tracking |

- All models run in OpenVINO™ Intermediate Representation (IR) format
- Inference supported on **CPU**, **GPU**, and **NPU** (configurable per pipeline)
- Default inference device: **NPU** (recommended for best performance on Intel® Core Ultra)

## Content Search Pipeline

### Content Search Supported Models

| Model | Purpose | Device |
| ----- | ------- | ------ |
| **Qwen3-VL-8B-Instruct** | Vision Language Model for video summarization and Q&A | GPU |
| **CLIP/clip-xlm-roberta-base-vit-b-32** | Visual embedding for images and video frames | CPU |
| **intfloat/multilingual-e5-small** | Text embedding for document chunks | CPU |
| **BAAI/bge-reranker-base** | Cross-encoder reranking for search results | CPU |

### Supported File Formats

| Category | Extensions |
| -------- | ---------- |
| **Video** | `.mp4` |
| **Document** | `.txt`, `.pdf`, `.docx`, `.doc`, `.pptx`, `.ppt`, `.xlsx`, `.xls`, `.html`, `.htm`, `.xml`, `.md` |
| **Image** | `.jpg`, `.jpeg`, `.png` |
