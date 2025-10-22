# Tutorial 2: Video Decode and Tiled Display

This tutorial demonstrates advanced video processing capabilities using Intel's hardware-accelerated video decoding and composition. You'll learn to decode multiple video streams simultaneously and display them in a tiled layout on a 4K monitor using VAAPI (Video Acceleration API) and GStreamer.

## Overview

Multi-stream video processing is essential for applications like video surveillance, broadcasting, and media production. This tutorial showcases how Intel's hardware acceleration can efficiently decode and composite 16 simultaneous video streams into a single 4K display output, demonstrating the power of Intel® Quick Sync Video technology.

> ** Platform Compatibility**  
> This tutorial requires Intel® Core™ or Intel® Core™ Ultra processors with integrated graphics. Intel® Xeon® processors without integrated graphics are not supported for this specific use case.

## Time to Complete

**Estimated Duration:** 15-20 minutes

## Learning Objectives

Upon completion of this tutorial, you will be able to:

- Configure hardware-accelerated video decoding with VAAPI
- Create complex GStreamer pipelines for multi-stream processing
- Implement tiled video composition for 4K display output
- Monitor video decoding performance and frame rates
- Understand Intel® Quick Sync Video acceleration benefits
- Deploy containerized video processing applications

## Prerequisites

Before starting this tutorial, ensure you have:

- Metro Vision AI SDK installed and configured
- Intel® Core™ or Intel® Core™ Ultra processor with integrated graphics
- 4K monitor or display capable of 3840x2160 resolution
- Docker installed and running on your system
- X11 display server configured
- Basic familiarity with GStreamer concepts

## System Requirements

- **Operating System:** Ubuntu 22.04 LTS or Ubuntu 24.04 LTS
- **Processor:** Intel® Core™ or Intel® Core™ Ultra with integrated graphics
- **Memory:** Minimum 8GB RAM (16GB recommended for smooth performance)
- **Display:** 4K monitor (3840x2160) or compatible display
- **Storage:** 2GB free disk space for video files
- **Graphics:** Intel integrated graphics with VAAPI support

## Tutorial Steps

### Step 1: Create Working Directory and Download Video Content

Create a dedicated workspace and download the sample video for multi-stream processing:

```bash
# Create working directory structure
mkdir -p ~/metro/metro-vision-tutorial-2/videos/
cd ~/metro/metro-vision-tutorial-2

# Download Big Buck Bunny sample video (Creative Commons licensed)
wget -O videos/Big_Buck_Bunny.mp4 "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/1080/Big_Buck_Bunny_1080_10s_30MB.mp4s"
```

**Alternative Download Method:**
If the above link doesn't work, you can download from the official source:
```bash
# Alternative: Download from Internet Archive
wget -O videos/Big_Buck_Bunny.mp4 "https://archive.org/download/BigBuckBunny_124/Content/big_buck_bunny_720p_surround.mp4"
```

### Step 2: Create Multi-Stream Video Processing Script

Create a GStreamer pipeline script that will decode and compose 16 video streams into a 4x4 tiled display:

```bash
# Create the decode script
cat > decode.sh << 'EOF'
#!/bin/bash

# Video input file path
VIDEO_IN=videos/Big_Buck_Bunny.mp4

# Verify video file exists
if [ ! -f "$VIDEO_IN" ]; then
    echo "Error: Video file $VIDEO_IN not found!"
    exit 1
fi

echo "Starting 4x4 tiled video decode pipeline..."
echo "Video source: $VIDEO_IN"
echo "Target resolution: 3840x2160 (4K)"
echo "Individual tile size: 960x540"

# GStreamer pipeline for 4x4 tiled video composition
gst-launch-1.0 \
    vacompositor name=comp0 \
        sink_1::xpos=0    sink_1::ypos=0    sink_1::alpha=1 \
        sink_2::xpos=960  sink_2::ypos=0    sink_2::alpha=1 \
        sink_3::xpos=1920 sink_3::ypos=0    sink_3::alpha=1 \
        sink_4::xpos=2880 sink_4::ypos=0    sink_4::alpha=1 \
        sink_5::xpos=0    sink_5::ypos=540  sink_5::alpha=1 \
        sink_6::xpos=960  sink_6::ypos=540  sink_6::alpha=1 \
        sink_7::xpos=1920 sink_7::ypos=540  sink_7::alpha=1 \
        sink_8::xpos=2880 sink_8::ypos=540  sink_8::alpha=1 \
        sink_9::xpos=0    sink_9::ypos=1080 sink_9::alpha=1 \
        sink_10::xpos=960 sink_10::ypos=1080 sink_10::alpha=1 \
        sink_11::xpos=1920 sink_11::ypos=1080 sink_11::alpha=1 \
        sink_12::xpos=2880 sink_12::ypos=1080 sink_12::alpha=1 \
        sink_13::xpos=0    sink_13::ypos=1620 sink_13::alpha=1 \
        sink_14::xpos=960  sink_14::ypos=1620 sink_14::alpha=1 \
        sink_15::xpos=1920 sink_15::ypos=1620 sink_15::alpha=1 \
        sink_16::xpos=2880 sink_16::ypos=1620 sink_16::alpha=1 \
    ! vapostproc ! xvimagesink display=:0 sync=false \
\
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_1 \
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_2 \
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_3 \
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_4 \
\
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_5 \
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_6 \
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_7 \
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_8 \
\
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_9 \
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_10 \
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_11 \
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_12 \
\
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_13 \
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_14 \
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_15 \
    filesrc location=${VIDEO_IN} ! qtdemux ! vah264dec ! gvafpscounter ! vapostproc scale-method=fast ! video/x-raw,width=960,height=540 ! comp0.sink_16

EOF
```

### Understanding the GStreamer Pipeline

The script creates a complex pipeline with these key components:

**Pipeline Architecture:**
- **Input Sources**: 16 identical video file streams
- **Decoder**: `vah264dec` - Hardware-accelerated H.264 decoding using VAAPI
- **Scaling**: `vapostproc` - Hardware-accelerated video post-processing and scaling
- **Composition**: `vacompositor` - Hardware-accelerated video composition
- **Output**: `xvimagesink` - X11-based video display

**Tiled Layout Configuration:**
```
┌─────────┬─────────┬─────────┬─────────┐
│ Stream1 │ Stream2 │ Stream3 │ Stream4 │  ← Row 1 (y=0)
│  0,0    │ 960,0   │1920,0   │2880,0   │
├─────────┼─────────┼─────────┼─────────┤
│ Stream5 │ Stream6 │ Stream7 │ Stream8 │  ← Row 2 (y=540)
│  0,540  │ 960,540 │1920,540 │2880,540 │
├─────────┼─────────┼─────────┼─────────┤
│ Stream9 │Stream10 │Stream11 │Stream12 │  ← Row 3 (y=1080)
│ 0,1080  │960,1080 │1920,1080│2880,1080│
├─────────┼─────────┼─────────┼─────────┤
│Stream13 │Stream14 │Stream15 │Stream16 │  ← Row 4 (y=1620)
│ 0,1620  │960,1620 │1920,1620│2880,1620│
└─────────┴─────────┴─────────┴─────────┘
```

**Performance Optimizations:**
- **VAAPI Acceleration**: Hardware-accelerated decoding, scaling, and composition
- **Fast Scaling**: `scale-method=fast` for optimal performance
- **Async Display**: `sync=false` to prevent frame dropping

### Step 3: Prepare Environment and Permissions

Configure the execution environment for the containerized video processing:

```bash
# Make the script executable
chmod +x decode.sh

# Enable X11 forwarding for Docker containers
xhost +local:docker

# Verify GPU device availability
ls -la /dev/dri/

# Check Intel GPU support
vainfo --display drm --device /dev/dri/renderD128
```

### Step 4: Execute Multi-Stream Video Processing

Launch the containerized multi-stream decode and composition pipeline:

```bash
# Set up GPU device access
export DEVICE=/dev/dri/renderD128
export DEVICE_GRP=$(ls -g $DEVICE | awk '{print $3}' | xargs getent group | awk -F: '{print $3}')

# Execute the multi-stream video processing
docker run -it --rm --net=host \
  -e no_proxy=$no_proxy \
  -e https_proxy=$https_proxy \
  -e socks_proxy=$socks_proxy \
  -e http_proxy=$http_proxy \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  --device /dev/dri --group-add ${DEVICE_GRP} \
  -e DISPLAY=$DISPLAY \
  -v $HOME/.Xauthority:/home/dlstreamer/.Xauthority:ro \
  -v $PWD/videos:/home/dlstreamer/videos:ro \
  -v $PWD/decode.sh:/home/dlstreamer/decode.sh:ro \
  intel/dlstreamer:2025.1.2-ubuntu24 \
  /home/dlstreamer/decode.sh
```

### Step 5: Monitor Performance and Results

The application will display a 4x4 tiled video composition on your 4K monitor. You should see:

![4x4 Video Streaming Result](images/intel-edge-ai-box-4x4-video-streaming.png)

**Performance Monitoring:**
Monitor system resources during playback:

```bash
# In a separate terminal, monitor GPU utilization
sudo intel_gpu_top

# Monitor CPU and memory usage
htop

# Check video decoder utilization
cat /sys/class/drm/card0/gt/gt0/rc6_residency_ms
```


### Step 6: Stop the Application

To stop the video processing pipeline:

```bash
# Press Ctrl+C in the terminal running the Docker container
# Or use Docker commands to stop
docker ps  # Find the container ID
docker stop <container_id>
```

Clean up the environment:

```bash
# Restore X11 security (optional)
xhost -local:docker

# Clean up any temporary files
docker system prune -f
```


## Understanding the Technology

### Intel® Quick Sync Video Technology

This tutorial leverages Intel's hardware-accelerated video processing capabilities:

**Hardware Acceleration Benefits:**
- **Dedicated Video Engines**: Separate silicon for video decode/encode operations
- **CPU Offloading**: Frees CPU resources for other computational tasks  
- **Power Efficiency**: Lower power consumption compared to software decoding
- **Parallel Processing**: Multiple decode engines can process streams simultaneously

### VAAPI Integration

**Video Acceleration API (VAAPI)** provides:
- **Hardware Abstraction**: Unified interface across Intel graphics generations
- **Pipeline Optimization**: Direct GPU memory access without CPU copies
- **Format Support**: Hardware acceleration for H.264, H.265, VP9, and AV1 codecs
- **Scaling Operations**: Hardware-accelerated resize and format conversion

### GStreamer Pipeline Architecture

The tutorial demonstrates advanced GStreamer concepts:

**Element Types:**
- **Source Elements**: `filesrc` - File input
- **Demuxer Elements**: `qtdemux` - Container format parsing  
- **Decoder Elements**: `vah264dec` - Hardware-accelerated decoding
- **Transform Elements**: `vapostproc` - Hardware scaling and format conversion
- **Compositor Elements**: `vacompositor` - Multi-stream composition
- **Sink Elements**: `xvimagesink` - Display output

**Pipeline Benefits:**
- **Zero-Copy Operations**: Direct GPU memory transfers
- **Parallel Processing**: Concurrent decode of multiple streams
- **Dynamic Reconfiguration**: Runtime pipeline modifications
- **Error Recovery**: Robust handling of stream issues