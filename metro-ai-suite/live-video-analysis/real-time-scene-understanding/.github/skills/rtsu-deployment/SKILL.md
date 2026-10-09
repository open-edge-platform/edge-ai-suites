---
name: rtsu-deployment
description: Deploy and manage Real Time Scene Understanding with Docker Compose, including environment setup, model preflight, health checks, and shutdown.
license: Apache-2.0
---

<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Real Time Scene Understanding Deployment

Use this skill when the user asks to configure, build, start, stop, restart, or inspect the Docker Compose deployment.

## Prerequisites

- Run commands from the repository root.
- Confirm Docker Engine and Docker Compose are installed.
- Confirm the required Intel runtime and device access are available when using GPU or NPU inference.
- Do not print or commit `.env`, model weights, Hugging Face tokens, or storage credentials.

## Configure the environment

Create or refresh the local environment file with:

```bash
bash scripts/setup_env.sh
```

Use `bash scripts/setup_env.sh --force` only when the user explicitly wants an existing `.env` overwritten. Review model, device, port, host, and storage settings before starting the stack.

## Model preflight

Before starting the stack, confirm that the directories for `ALERT_VLM_MODEL` and `DEEP_ANALYZER_MODEL` exist under `ov_models/<device-lowercase>/<model-name>/`. The models are mounted read-only at `/models` in the application container. If a model is missing, follow the model download guide before deploying.

Confirm that the selected deep-analyzer model supports video input. Confirm the required Intel runtime and `/dev/dri` or configured NPU device before selecting GPU or NPU inference.

## Validate and build

Validate the rendered Compose configuration without starting services:

```bash
docker compose config --quiet
```

Build the application image from source:

```bash
docker compose build
```

Use `COPYLEFT_SOURCES=true docker compose build` only when the user requests inclusion of third-party copyleft source packages.

## Start and verify

Start the stack in the background:

```bash
docker compose up -d
```

Check service state:

```bash
docker compose ps
```

Check the application health endpoint:

```bash
curl --fail http://localhost:${PORT:-9100}/api/health
```

The dashboard is normally available at `http://<host>:9100`. The host port is controlled by `PORT`; the container port remains `9100`.

## Stop and clean up

Stop the services with:

```bash
docker compose down
```

Do not remove named volumes or delete model files unless the user explicitly asks for data cleanup. SeaweedFS data is stored in the `seaweedfs-data` volume.

## Completion criteria

Report the Compose state, health endpoint result, and any service logs that explain a failure. Do not claim deployment success based only on `docker compose up`; verify health.