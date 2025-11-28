# Metro Vision AI SDK - Tutorial 5

This tutorial will guide you through profiling and monitoring performance of Metro Vision AI workloads using command-line tools. You'll learn to use `perf`, `htop`, and `intel_gpu_top` to analyze system performance while running DLStreamer Pipeline Server or OpenVINO applications.

## Prerequisites

- Ubuntu 22.04 or later
- Docker installed and configured
- Intel hardware with CPU and/or GPU
- Administrative privileges for performance monitoring
- Internet connection for downloading model and video files

## Step 1: Install Performance Monitoring Tools and Docker

Install the required command-line performance monitoring tools and Docker:

```bash
# Update system packages
sudo apt update

# Install performance monitoring tools
sudo apt install -y htop intel-gpu-tools

# Install Docker (if not already installed)
sudo apt install -y docker.io

# Add user to docker group (requires logout/login)
sudo usermod -aG docker $USER

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Verify installations
htop --version
intel_gpu_top --help
docker --version
```

## Step 2: Verify System Hardware

Check your system hardware for monitoring:

```bash
# Check CPU information
lscpu | grep -E "Model name|CPU\(s\)"

# Check GPU availability
lspci | grep -i vga

# Check Intel GPU device files
ls -la /dev/dri/
```

## Step 3: Start Your Metro Vision AI Workload

Create and start a DLStreamer pipeline that continuously runs in the background for profiling:

```bash
mkdir -p ~/metro/metro-vision-tutorial-5
cd ~/metro/metro-vision-tutorial-5

# Download sample video for object detection
wget -O bottle-detection.mp4 https://storage.openvinotoolkit.org/test_data/videos/bottle-detection.mp4

# Download YOLOv10s model using DLStreamer container
docker run --rm --user=root \
  -e http_proxy -e https_proxy -e no_proxy \
  -v "${PWD}:/home/dlstreamer/" \
  intel/dlstreamer:2025.1.2-ubuntu24 \
  bash -c "export MODELS_PATH=/home/dlstreamer && /opt/intel/dlstreamer/samples/download_public_models.sh yolov10s"

# Create a continuous DLStreamer pipeline script
cat > metro_vision_pipeline.sh << 'EOF'
#!/bin/bash

# Metro Vision AI DLStreamer Pipeline for Performance Testing using Docker
CURRENT_DIR=$(pwd)
MODEL_PATH="$CURRENT_DIR/public/yolov10s/FP32/yolov10s.bin"
VIDEO_PATH="$CURRENT_DIR/bottle-detection.mp4"

echo "Starting Metro Vision AI Pipeline with Docker DLStreamer..."
echo "Model: $MODEL_PATH"
echo "Video: $VIDEO_PATH"
echo "Device: $DEVICE"

# Check if model and video exist
if [[ ! -f "$MODEL_PATH" ]]; then
    echo "Error: Model file not found at $MODEL_PATH"
    exit 1
fi

if [[ ! -f "$VIDEO_PATH" ]]; then
    echo "Error: Video file not found at $VIDEO_PATH"
    exit 1
fi


# Continuous loop to keep pipeline running
while true; do
    echo "$(date): Starting pipeline iteration..."

    # Run DLStreamer pipeline in Docker container with object detection
    docker run --rm \
        --device /dev/dri:/dev/dri \
        -v "$CURRENT_DIR:/workspace" \
        -w /workspace \
        intel/dlstreamer:2025.1.2-ubuntu24  \
        gst-launch-1.0 \
            filesrc location=/workspace/bottle-detection.mp4 ! \
            qtdemux ! h264parse ! avdec_h264 ! \
            videoconvert ! \
            gvadetect model=/workspace/public/yolov10s/FP32/yolov10s.xml device="$DEVICE" ! \
            gvafpscounter ! \
            fakesink sync=false \
            2>/dev/null

    echo "$(date): Pipeline ended, restarting in 2 seconds..."
    sleep 2
done
EOF

export DEVICE=GPU
chmod +x metro_vision_pipeline.sh

# Start the pipeline in background
./metro_vision_pipeline.sh &
PIPELINE_PID=$!

echo "Metro Vision AI pipeline started with PID: $PIPELINE_PID"
echo "Use 'kill $PIPELINE_PID' to stop the pipeline when done profiling"
```

**Note**: This creates a continuously running Docker-based DLStreamer pipeline that processes real video using the YOLOv10s object detection model, providing a realistic AI workload for performance profiling. The pipeline runs in a Docker container with access to Intel GPU hardware.

## Step 4: Monitor Overall System Performance with htop

Launch htop to monitor real-time system performance:

```bash
# Start htop for real-time monitoring
htop
```

**What to observe:**

- CPU usage per core (bars at the top)
- Memory usage and available memory
- Running processes sorted by CPU usage
- Look for your Metro Vision AI processes

**Key shortcuts in htop:**

- `F6` - Sort by different columns (CPU%, MEM%)
- `F4` - Filter processes by name
- `q` - Quit htop

## Step 5: Monitor Intel GPU Performance

Use intel_gpu_top to monitor GPU usage during AI inference:

```bash
# Start Intel GPU monitoring
sudo intel_gpu_top
```

**What to observe:**

- Render/3D engine usage (shows AI inference workload)
- Video engine usage (shows video decode/encode)
- GPU frequency and power consumption
- Memory usage and bandwidth

## Step 6: Stop the Running Pipeline

When you're done profiling, stop the background pipeline:

```bash
# Stop the background DLStreamer pipeline
pkill -9 -f metro_vision_pipeline.sh
```

## Next Steps: Visual Pipeline and Platform Evaluation Tool (Vippet)

Now that you've learned to monitor AI workloads with command-line tools, take your performance analysis to the next level with **Vippet** - a visual tool for evaluating and optimizing AI pipelines.

### What is Vippet?

Vippet (Visual Pipeline and Platform Evaluation Tool) is an interactive web-based application that helps you:

- **Visualize Pipeline Performance**: See real-time metrics and graphs of your AI pipeline performance
- **Compare Configurations**: Test different hardware devices (CPU, GPU, NPU) and model configurations
- **Benchmark Workloads**: Measure throughput, latency, and resource utilization
- **Optimize Pipelines**: Identify bottlenecks and tune parameters for better performance
- **Generate Reports**: Create detailed performance reports for analysis and documentation

### Getting Started with Vippet

To learn more and get started with Vippet, visit the official documentation:

**📚 [Vippet Documentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html)**

The documentation includes:
- Installation instructions
- Quick start guides
- Tutorial videos
- Pipeline configuration examples
- Performance tuning best practices

### Why Use Vippet After This Tutorial?

After using `htop` and `intel_gpu_top` for basic monitoring, Vippet provides:

1. **Visual Analysis**: Interactive charts instead of terminal output
2. **Automated Testing**: Run multiple benchmark scenarios automatically
3. **Comparative Analysis**: Side-by-side comparison of different configurations
4. **Historical Data**: Track performance trends over time
5. **Export Capabilities**: Generate professional reports for stakeholders

Vippet complements the command-line monitoring skills you've learned in this tutorial by providing a comprehensive visual interface for deeper performance analysis and optimization.

## Summary

This tutorial provides a practical approach to profiling Metro Vision AI workloads using command-line tools:

### **What You've Learned:**

1. **Installing Tools**: Set up `htop` and `intel_gpu_top` for system monitoring
2. **System Monitoring**: Use `htop` for real-time CPU and memory monitoring
3. **GPU Profiling**: Monitor Intel GPU performance with `intel_gpu_top`
4. **Performance Analysis**: Understand resource utilization patterns

### **Key Monitoring Points:**

- **CPU Usage**: Monitor core utilization and identify bottlenecks
- **Memory Usage**: Track memory consumption and avoid swapping
- **GPU Utilization**: Monitor Intel GPU render engine usage
- **Process Performance**: Track specific AI application performance