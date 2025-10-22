# Tutorial 5: Profiling

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
sudo apt install -y htop intel-gpu-tools linux-tools-generic

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
perf --version
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
intel_gpu_top
```

**What to observe:**
- Render/3D engine usage (shows AI inference workload)
- Video engine usage (shows video decode/encode)
- GPU frequency and power consumption
- Memory usage and bandwidth

## Step 6: Profile CPU Performance with perf

Use perf to profile CPU performance and identify hotspots:

```bash
# Find the process ID of the Docker DLStreamer pipeline
DOCKER_PID=$(pgrep -f "docker.*dlstreamer")
echo "Found Docker DLStreamer container PID: $DOCKER_PID"

# Also find the gst-launch process inside container
GST_PID=$(pgrep -f "gst-launch")
echo "Found gst-launch process PID: $GST_PID"

# Record performance data for 30 seconds (monitor Docker process)
sudo perf record -g -p $DOCKER_PID sleep 30

# Generate performance report
sudo perf report
```

**What to observe:**
- Function call hotspots and CPU cycles
- Call stack and execution paths
- Cache misses and memory access patterns

## Step 7: Collect System Statistics

Capture detailed system performance statistics:

```bash
# Monitor system statistics for 60 seconds
vmstat 1 60 > system_stats.log &

# Monitor memory usage
free -h -s 1 | head -20 > memory_usage.log &

# Let them run while your AI application is processing
```

## Step 8: Monitor Process-Specific Performance  

Monitor the specific performance of your AI processes:

```bash
# Find and monitor Docker DLStreamer pipeline processes
ps aux | grep -E "docker.*dlstreamer\|metro_vision_pipeline" | grep -v grep

# Monitor Docker container process with top
top -p $(pgrep -f "docker.*dlstreamer")

# Check Docker container processes and threads
docker ps --format "table {{.ID}}\t{{.Image}}\t{{.Status}}"
ps -T -p $(pgrep -f "docker.*dlstreamer")
```

## Step 9: Check Thermal and Power Status

Monitor system thermal status during AI workload:

```bash
# Check CPU temperature
sensors | grep Core

# Monitor power consumption (if available)  
sudo powertop --time=10

# Check CPU frequency scaling
cat /proc/cpuinfo | grep MHz | head -4
```

## Step 10: Generate Performance Summary Report

Create a simple performance summary from your monitoring:

```bash
# Create a performance summary report
cat > performance_summary.txt << EOF
Metro Vision AI Workload Performance Summary
Generated: $(date)

=== System Configuration ===
CPU: $(lscpu | grep "Model name" | cut -d: -f2 | xargs)
Memory: $(free -h | awk 'NR==2{print $2}')
GPU: $(lspci | grep -i vga | head -1)

=== AI Process Performance ===
Docker DLStreamer Pipeline Processes:
$(ps aux | grep -E "docker.*dlstreamer\|metro_vision_pipeline" | grep -v grep | awk '{printf "PID: %s, CPU: %s%%, MEM: %s%%, CMD: %s\n", $2, $3, $4, $11}')

Docker Containers:
$(docker ps --format "{{.ID}}: {{.Image}} ({{.Status}})" | grep dlstreamer)

Current System Load: $(cat /proc/loadavg)
Current Memory Usage: $(free -h | awk 'NR==2{printf "Used: %s/%s (%.1f%%)", $3, $2, $3/$2*100}')

=== Recommendations ===
- Review htop output for CPU usage patterns
- Check intel_gpu_top for GPU utilization efficiency  
- Analyze perf report for CPU bottlenecks
- Monitor thermal status for throttling

EOF

echo "Performance summary saved to: performance_summary.txt"
cat performance_summary.txt

# Stop the background pipeline when profiling is complete
echo ""
echo "To stop the background DLStreamer pipeline:"
echo "kill \$(pgrep -f metro_vision_pipeline)"
```

## Summary

This tutorial provides a practical approach to profiling Metro Vision AI workloads using command-line tools:

### **What You've Learned:**
1. **Installing Tools**: Set up `htop`, `intel_gpu_top`, and `perf` for system monitoring
2. **System Monitoring**: Use `htop` for real-time CPU and memory monitoring  
3. **GPU Profiling**: Monitor Intel GPU performance with `intel_gpu_top`
4. **CPU Profiling**: Use `perf` to identify performance bottlenecks and hotspots
5. **System Analysis**: Collect comprehensive performance data
6. **Performance Reporting**: Generate actionable performance summaries

### **Key Monitoring Points:**
- **CPU Usage**: Monitor core utilization and identify bottlenecks
- **Memory Usage**: Track memory consumption and avoid swapping
- **GPU Utilization**: Monitor Intel GPU render engine usage
- **Thermal Status**: Ensure no thermal throttling occurs
- **Process Performance**: Track specific AI application performance