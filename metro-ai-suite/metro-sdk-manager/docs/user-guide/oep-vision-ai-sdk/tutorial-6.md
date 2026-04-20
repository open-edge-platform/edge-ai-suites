# OEP Vision AI SDK - Tutorial 6

This tutorial walks you through deploying Intel® SceneScape using the prebuilt Docker images already downloaded by the OEP Vision AI SDK install script.

## Overview

Intel® SceneScape goes beyond single-camera vision AI by fusing data from multiple cameras and sensors into a unified scene graph. It enables spatial awareness, multimodal object tracking, and scene analytics for smart city, retail, and industrial applications.

## Time to Complete

**Estimated Duration:** 10–15 minutes

## Learning Objectives

Upon completion of this tutorial, you will be able to:

- Deploy the SceneScape demo using prebuilt container images
- Access and explore the SceneScape web UI
- Manage SceneScape services with Docker Compose profiles

## Prerequisites

- OEP Vision AI SDK installed (the install script downloads SceneScape images and clones the repo)
- Docker and Docker Compose installed and running

## Tutorial Steps

### Step 1: Navigate to the SceneScape Repository

The OEP Vision AI SDK install script already cloned SceneScape. Navigate to it:

```bash
cd ~/oep/scenescape
```

### Step 2: Initialize Secrets and Models

Generate TLS certificates and download the required OpenVINO models:

```bash
make init-secrets install-models
```

### Step 3: Deploy the SceneScape Demo

Set a super user password and start the demo:

```bash
export SUPASS=<your-password>
make demo
```

> **Note:** Choose a strong password. This is the admin password for the web UI, not your system password.

### Step 4: Access the Web UI

Open a browser and navigate to:

- **Local:** `https://localhost`
- **Remote:** `https://<ip_address>` or `https://<hostname>`

If you see a certificate warning, this is expected (SceneScape uses a self-signed certificate). Click through to proceed.

Log in with:

- **Username:** `admin`
- **Password:** The value you set for `SUPASS`

The demo includes two pre-configured scenes running from stored video data that you can explore.

To stop the services:

```bash
docker compose --profile controller down --remove-orphans
```

## Next Steps

- [SceneScape Tutorial](https://github.com/open-edge-platform/scenescape/blob/main/docs/user-guide/tutorial.md): Follow examples to explore core SceneScape functionality
- [How to Use the 3D UI](https://github.com/open-edge-platform/scenescape/blob/main/docs/user-guide/how-to-use-3D-UI.md): Explore the 3D visualization interface
- [How to Integrate Cameras and Sensors](https://github.com/open-edge-platform/scenescape/blob/main/docs/user-guide/how-to-integrate-cameras-and-sensors.md): Connect live cameras and sensors
- [How to Create a New Scene](https://github.com/open-edge-platform/scenescape/blob/main/docs/user-guide/building-a-scene/how-to-create-new-scene.md): Build your own scene from scratch
- [API Reference](https://github.com/open-edge-platform/scenescape/blob/main/docs/user-guide/api-reference.md): Full REST API documentation
