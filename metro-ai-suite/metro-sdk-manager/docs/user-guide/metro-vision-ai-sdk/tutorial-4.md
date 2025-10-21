# Tutorial 4: Video Analytics Pipelines

This tutorial demonstrates how to build sophisticated video analytics pipelines using Intel® DL Streamer framework. You'll learn to create real-time human pose estimation applications, understand GStreamer pipeline architecture, and develop custom video analytics solutions for computer vision applications.

## Overview

Intel® DL Streamer is a comprehensive video analytics framework built on GStreamer technology that enables rapid development of AI-powered video processing applications. This tutorial focuses on human pose estimation, a critical computer vision task used in sports analysis, healthcare monitoring, security systems, and human-computer interaction applications.

Human pose estimation involves detecting and tracking key points on the human body (joints, limbs) to understand body posture and movement patterns. This technology enables applications like fitness tracking, ergonomic analysis, action recognition, and assistive technologies.

## Time to Complete

**Estimated Duration:** 25-30 minutes

## Learning Objectives

Upon completion of this tutorial, you will be able to:

- Build advanced video analytics pipelines using Intel® DL Streamer framework
- Implement real-time human pose estimation with OpenVINO optimization
- Understand GStreamer plugin architecture and pipeline development
- Create custom video processing workflows for computer vision applications
- Optimize performance for real-time video analytics on Intel hardware
- Deploy containerized video analytics solutions
- Integrate multiple AI models in video processing pipelines
- Develop production-ready video analytics applications

## Prerequisites

Before starting this tutorial, ensure you have:

- Metro Vision AI SDK installed and configured
- Docker installed and running on your system
- Understanding of computer vision and AI inference concepts
- Basic familiarity with GStreamer framework
- X11 display server configured for GUI applications
- Internet connection for downloading models and video content

## System Requirements

- **Operating System:** Ubuntu 22.04 LTS or Ubuntu 24.04 LTS
- **Processor:** Intel® Core™, Intel® Core™ Ultra, or Intel® Xeon® processors
- **Memory:** Minimum 8GB RAM (16GB recommended for complex pipelines)
- **Storage:** 4GB free disk space for models, videos, and intermediate files
- **Graphics:** Intel integrated graphics or discrete GPU (recommended for acceleration)
- **Display:** Monitor capable of displaying real-time video output

## Tutorial Steps

### Step 1: Create Working Directory and Download Assets

Set up your workspace and download the required video content and AI models:

```bash
# Create working directory structure
mkdir -p ~/metro/metro-vision-tutorial-4/{models/intel/human-pose-estimation-0001/FP32,output}
cd ~/metro/metro-vision-tutorial-4

# Download sample video for human pose estimation
wget -O face-demographics-walking.mp4 \
  "https://github.com/intel-iot-devkit/sample-videos/raw/master/face-demographics-walking.mp4"

# Download human pose estimation model files
wget -O models/intel/human-pose-estimation-0001/FP32/human-pose-estimation-0001.xml \
  "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/human-pose-estimation-0001/FP32/human-pose-estimation-0001.xml"

wget -O models/intel/human-pose-estimation-0001/FP32/human-pose-estimation-0001.bin \
  "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/human-pose-estimation-0001/FP32/human-pose-estimation-0001.bin"

wget -O models/intel/human-pose-estimation-0001/human-pose-estimation-0001.json \
  "https://raw.githubusercontent.com/dlstreamer/dlstreamer/master/samples/gstreamer/model_proc/intel/human-pose-estimation-0001.json"
```

### Step 2: Understand Human Pose Estimation Model

**Model Architecture:**
- **Model Name**: human-pose-estimation-0001
- **Framework**: OpenVINO optimized model from Intel Model Zoo
- **Input**: 256x456 RGB image
- **Output**: 17 keypoints representing major body joints
- **Precision**: FP32 for optimal accuracy

### Step 3: Configure Environment for DL Streamer

Prepare the environment for containerized video analytics:

```bash
# Enable X11 forwarding for GUI applications
xhost +local:docker

# Verify Docker access to display
echo "Display: $DISPLAY"
echo "X11 Auth: $HOME/.Xauthority"
```

### Step 4: Run Basic Human Pose Estimation Pipeline

Execute the pre-built human pose estimation pipeline using DL Streamer:

```bash
# Run human pose estimation with DL Streamer container
docker run -it --rm --net=host \
  -e DISPLAY=$DISPLAY \
  -e no_proxy=$no_proxy \
  -e https_proxy=$https_proxy \
  -e http_proxy=$http_proxy \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v ${PWD}:/home/dlstreamer/data \
  -v $HOME/.Xauthority:/home/dlstreamer/.Xauthority:ro \
  intel/dlstreamer:2025.1.2-ubuntu24 \
  bash -c "export MODELS_PATH=/home/dlstreamer/data/models && \
           /opt/intel/dlstreamer/samples/gstreamer/gst_launch/human_pose_estimation/human_pose_estimation.sh \
           /home/dlstreamer/data/face-demographics-walking.mp4"
```

**Pipeline Execution Features:**
- Real-time human pose detection and visualization
- Skeletal overlay on detected persons
- Keypoint confidence scoring
- Multi-person pose estimation support
- Hardware-accelerated inference using OpenVINO

![Human Pose Estimation](images/tutorial_dlstreamer_container.png)