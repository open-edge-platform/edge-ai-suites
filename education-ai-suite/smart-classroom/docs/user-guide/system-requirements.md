# System Requirements

This page provides detailed hardware, software, platform requirements, and supported models to help you set up and run the application efficiently.

## Software and Hardware Requirements

- **OS**: Windows 11
- **Processor**: Intel® Core Ultra Series 1 (with integrated GPU support)
- **Memory**: 32 GB RAM (minimum recommended)
- **Storage**: At least 50 GB free (for models and logs)
- **GPU/Accelerator**: Intel® iGPU (Core Ultra Series 1, Arc GPU, or higher) for summarization acceleration
- **Python**: 3.12 or above
- **Node.js**: v18+ (for frontend)

## Supported Models  

### ASR (Automatic Speech Recognition)  

- **Whisper (all models supported)**  
  - Recommended: `whisper-small` or lower for CPU efficiency  
  - Runs on **CPU** (Whisper is CPU-centric)  
- **FunASR (Paraformer)**  
  - Recommended for **Chinese transcription** (`paraformer-zh`)
-  Supports transcription of audio files up to 45 minutes

###  Summarization (LLMs)  
- **Qwen Models (OpenVINO / IPEX)**  
  - `Qwen2.0-7B-Instruct`  
  -  `Qwen2.5-7B-Instruct`
-  Summarization supports up to 7,500 tokens (≈ 45 minutes of audio) on GPU

###  Supported Weight Formats  
- **int8** → Recommended for lower-end CPUs (fast + efficient)  
- **fp16** → Recommended for higher-end systems (better accuracy, GPU acceleration)  
- **int4** → Supported, but may reduce accuracy (use only if memory-constrained)  

 Run summarization on **GPU** (Intel® iGPU / Arc GPU) for faster performance.  
