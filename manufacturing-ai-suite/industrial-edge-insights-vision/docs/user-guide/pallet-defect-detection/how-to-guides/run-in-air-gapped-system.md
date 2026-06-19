# Run in Air-Gapped System

This guide explains how to run the Pallet Defect Detection application in an environment without internet access.

## Prerequisites

- Complete all steps in the **Set up the application** section of [Get Started](../get-started.md) while connected to the internet. This ensures all required models and videos are pre-downloaded before running in an air-gapped system.
- Ensure all required Docker images are pre-pulled while connected to the internet, as they cannot be downloaded in an air-gapped system.

## Configure for Air-Gapped System

1. **Set `HOST_IP` to `127.0.0.1`** in the `.env` file:

   ```bash
   HOST_IP=127.0.0.1
   ```

2. **Enable the STUN server override** in `docker-compose.yml`. Uncomment the `extra_hosts` entry under the `dlstreamer-pipeline-server` service so that STUN lookups are redirected locally instead of reaching out to the internet:

   ```yaml
   dlstreamer-pipeline-server:
      extra_hosts:
      - "stun.l.google.com:127.0.0.1"
   ```

## Start the Application

1. Start the Docker application:

   ```bash
   docker compose up -d
   ```

2. Start the pipeline:

   ```bash
   ./sample_start.sh -p pallet_defect_detection
   ```

3. Open a browser and navigate to:

   ```text
   https://127.0.0.1/mediamtx/pdd/
   ```

   > **Note:** If you experience issues while streaming video on Firefox, it is recommended to use Google Chrome.

## Stop the Application

```bash
docker compose down -v
```
