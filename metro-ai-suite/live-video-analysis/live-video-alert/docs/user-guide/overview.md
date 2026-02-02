# Overview

Deploy AI-powered alerting for live video streams with OpenVINO Vision Language Models. Process RTSP streams, generate real-time alerts based on natural language prompts, and monitor them on a dashboard.

## Table of Contents

1. [Overview and Features](#overview-and-features)
2. [How the Application Works](#how-the-application-works)

## Overview and Features

### Use Cases

**Real-time Video Analytics**: Monitor security cameras, industrial equipment, or public spaces with AI-powered scene understanding and automatic alerting.

**Safety Monitoring**: Deploy prompts like "Is there a fire?" or "Is anyone wearing a safety vest?" to trigger immediate visual notifications.

**Custom Alerts**: Use natural language to define what constitutes an alert without retraining a model.

### Key Features

**Dynamic Alert Prompts**: Define and modify "Alerts" (prompts) in real-time through the UI without redeploying.

**Real-time Event Broadcasting**: Server-Sent Events (SSE) deliver instant alerts to the dashboard with low latency.

**Modular Architecture**: Decoupled ingestion, analysis, and event broadcasting for scalability.

**Intel® Hardware Optimized**: Designed for high-performance inference on Intel® CPUs and GPUs via OpenVINO.

## How the Application Works

The application ingests RTSP streams, performs VLM inference, and delivers real-time alerts through a web dashboard.

### Data Flow

```
RTSP Source → StreamManager (OpenCV/Circular Buffer)
            ↓
       AgentManager (Orchestrator) ↔ VLM Service (OpenAI-compatible API)
            ↓
       EventManager (SSE Pub/Sub) → Dashboard UI
```
