# How to use NPU for inference

## Pre-requisites
Machine with NPU is available

## Configure and deploy NPU pipelines

In `edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/src/dlstreamer-pipeline-server/config.json` the following NPU pipelines are available. Set `"auto_start": true` for each of them.
- intersection-cam1-npu
- intersection-cam2-npu
- intersection-cam3-npu
- intersection-cam4-npu

Also, set `"auto_start": false` for the other pipelines in the same configuration file.
- intersection-cam1
- intersection-cam2
- intersection-cam3
- intersection-cam4

Start the application with:
`docker compose up -d`