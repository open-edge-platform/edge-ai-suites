<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->
# Federal Aerospace — Handheld Multi-Modal Application

This package contains:

- `handheld-multi-modal/` — Federal and Aerospace AI Suite's Handheld Multi-Modal application (Docker Compose stack).
- `vippet-fedaero/`       — Visual Pipeline and Platform Evaluation Tool, pre-checked-out at the pinned revision.
- `run.sh`                — Convenience wrapper around `make deploy` and `make down`.

## Prerequisites

- Docker Engine version 24 and later, with the Docker Compose v2 plugin (`docker compose ...`).
- Intel® GPU with OpenVINO™ driver (iGPU or discrete GPU based on the Xe architecture).

## Running

```bash
./run.sh up      # Deploy Visual Pipeline and Platform Evaluation Tool and HandHeld Multi-Modal stack (default)
./run.sh down    # Stop both stacks
./run.sh logs    # Tail logs from the HandHeld Multi-Modal stack
```

Or invoke `make` directly:

```bash
cd handheld-multi-modal
make deploy        # standard GPU
make deploy-cdi    # CDI and SR-IOV
make down          # stop everything
```

`make deploy` configures Visual Pipeline and Platform Evaluation Tool, starts it, waits for the Docker network, and then brings up the HandHeld Multi-Modal stack. The pinned Visual Pipeline and Platform Evaluation Tool revision is recorded in `vippet/.vippet-ref`.
