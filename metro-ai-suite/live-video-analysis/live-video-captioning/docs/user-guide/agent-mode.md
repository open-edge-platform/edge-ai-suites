# Agent Mode

Agent Mode is an optional feature in Live Video Captioning that enables alert-style visual feedback for binary classification prompts. When enabled, the application provides enhanced visual indicators for "Yes" or "No" responses, making it ideal for automated monitoring and surveillance scenarios.

## Overview

In Agent Mode, the application:

- Changes the default prompt to: **"Is there an accident in the stream? Just Answer with a Yes or No"**
- Applies distinct visual styling to "Yes" and "No" responses in the caption display
- Updates the application title to "Live Video Captioning and Alerts"
- Provides clear alert indicators for detections (Green vs Red)

This mode is particularly useful for:

- **Accident Detection**: Monitor traffic streams for incidents
- **Security Monitoring**: Detect unauthorized access or suspicious activity
- **Safety Compliance**: Verify safety protocols are being followed
- **Anomaly Detection**: Identify unusual events in video feeds

## Enabling Agent Mode

### Option 1: Environment Variable in `.env` File

Add or modify the `AGENT_MODE` variable in your `.env` file:

```bash
# .env file
WHIP_SERVER_IP=mediamtx
WHIP_SERVER_PORT=8889
WHIP_SERVER_TIMEOUT=30s
PROJECT_NAME=live-captioning
HOST_IP=<HOST_IP>
EVAM_HOST_PORT=8040
EVAM_PORT=8080
DASHBOARD_PORT=4173
WEBRTC_PEER_ID=stream
METADATA_POLL_SECONDS=0.5
AGENT_MODE=True   # Enable Agent Mode
```

## Visual Indicators

When Agent Mode is enabled:

| Response | Visual Style |
|----------|--------------|
| **Yes** | Red/Alert highlighting indicating a positive detection |
| **No** | Green/Normal highlighting indicating no detection |

## Custom Prompts

While Agent Mode sets a default accident detection prompt, you can customize the prompt in the dashboard UI to suit your specific use case. The key requirement is that your prompt should elicit a "Yes" or "No" response for proper alert styling.

Example prompts for different scenarios:

- **Fire Detection**: "Is there a fire or smoke visible in the stream? Just Answer with a Yes or No"
- **Crowd Detection**: "Is there a large crowd gathering? Just Answer with a Yes or No"
- **Vehicle Detection**: "Is there a stopped vehicle blocking the road? Just Answer with a Yes or No"
- **PPE Compliance**: "Is the person wearing a safety helmet? Just Answer with a Yes or No"

## Troubleshooting

### Agent Mode Not Activating

1. Verify the `AGENT_MODE` environment variable is set correctly in your `.env` file
2. Ensure Docker Compose picks up the environment variable:
   ```bash
   docker compose down
   docker compose up
   ```
3. Check the application title - it should display "Live Video Captioning and Alerts"

### Alert Styling Not Appearing

- Ensure your prompt is designed to receive "Yes" or "No" responses
- Check that the VLM model is generating clear binary responses
- Verify the metadata stream is connected (check the status indicator)

## Next Steps

- [Get Started](./get-started.md) - Basic setup and configuration
- [API Reference](./api-reference.md) - REST API documentation
- [System Requirements](./system-requirements.md) - Hardware and software requirements
