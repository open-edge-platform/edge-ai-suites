# How to use GPU for inference

## Pre-requisites
Machine with GPU is available

## Configure and deploy GPU pipelines

In `edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/src/dlstreamer-pipeline-server/config.json` the following GPU pipelines are available. Set `"auto_start": true` for each of them. 
- intersection-cam1-gpu
- intersection-cam2-gpu
- intersection-cam3-gpu
- intersection-cam4-gpu

Also, set `"auto_start": false` for the other pipelines in the same configuration file.
- intersection-cam1
- intersection-cam2
- intersection-cam3
- intersection-cam4

Start the application with:
`docker compose up -d`

Note: If you have multiple GPUs (integrated/discrete), please follow [this](https://dlstreamer.github.io/dev_guide/gpu_device_selection.html) DL Streamer document for selecting the GPU render device of your choice for VA codecs plugins.