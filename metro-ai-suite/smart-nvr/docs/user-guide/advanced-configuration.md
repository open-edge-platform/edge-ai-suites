# Advanced Configuration

This guide covers optional features and advanced setup options for Smart NVR.

## Enabling AI-Powered Event Descriptions (GenAI)

To enable Smart NVR's GenAI capabilities for intelligent event descriptions:

### 1. Ensure VLM Service Availability

Verify the VLM microservice is running and accessible at the configured endpoint.

[VLM Serving Documentation](https://github.com/open-edge-platform/edge-ai-libraries/blob/release-2026.2.0/microservices/vlm-openvino-serving/docs/user-guide/get-started.md)

### 2. Set Environment Variables

```bash
export NVR_GENAI=true
export VLM_SERVING_IP=<vlm-serving-device-ip>
export VLM_SERVING_PORT=<vlm-serving-port>
```

### 3. Run the Application

Re-run the application after [configuring the base environment](./get-started.md#step-2-configure-environment).

> **Important:**
>
> - This feature is experimental and may be unstable due to underlying Frigate GenAI implementation.
> - Requires VLM microservice to be running.
> - Disabled by default for system stability.
> - `NVR_GENAI` is mutually exclusive with `NVR_SCENESCAPE`. If `NVR_SCENESCAPE=true`, `NVR_GENAI` is automatically disabled. Setting both to `true` will cause an error.

## Custom Build Configuration

If using custom [build flags](./get-started/build-from-source.md#customizing-the-build),
ensure the same environment variables are set before running the setup script.
