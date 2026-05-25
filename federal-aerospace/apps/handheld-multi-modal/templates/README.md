<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->
# Federal Aerospace — Handheld Multi-Modal

This package contains:

- `handheld-multi-modal/` — Federal Aerospace handheld multi-modal application (docker compose stack).
- `vippet-fedaero/`       — Visual Pipeline and Platform Evaluation Tool, pre-checked-out at the pinned revision.
- `run.sh`                — convenience wrapper around `make deploy` / `make down`.

## Prerequisites

- Docker Engine 24+ with the Compose v2 plugin (`docker compose ...`).
- Intel GPU with OpenVINO driver (iGPU or discrete Xe GPU).

## Running

```bash
./run.sh up      # deploy vippet + handheld-multi-modal stack (default)
./run.sh down    # stop both stacks
./run.sh logs    # tail logs from the handheld-multi-modal stack
```

Or invoke make directly:

```bash
cd handheld-multi-modal
make deploy        # standard GPU
make deploy-cdi    # CDI / SR-IOV
make down          # stop everything
```

`make deploy` configures vippet, starts it, waits for the Docker network, then brings up the handheld-multi-modal stack. The pinned vippet revision is recorded in `vippet/.vippet-ref`.
