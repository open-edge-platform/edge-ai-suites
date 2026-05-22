# Federal Aerospace Application Blueprint

This package contains:

- `handheld-multi-modal/` — Federal Aerospace handheld multi-modal application (docker compose stack).
- `vippet/`    — Visual Pipeline and Platform Evaluation Tool, sparse-checked-out
                 from [open-edge-platform/edge-ai-libraries](https://github.com/open-edge-platform/edge-ai-libraries).
- `run.sh`     — convenience script that brings up both docker compose stacks.

## Prerequisites

- Docker Engine 24+ with the Compose v2 plugin (`docker compose ...`).
- The package extracted under `/opt/intel/eas/fedaero/app-blueprint/`.

## Running

```bash
cd /opt/intel/eas/fedaero/app-blueprint
./run.sh up      # start both stacks (default)
./run.sh down    # stop both stacks
./run.sh logs    # tail logs from both stacks
```

`run.sh up` runs, in order:

1. `docker compose -f handheld-multi-modal/docker-compose.yml up -d`
2. `docker compose -f vippet/compose.yml up -d`

The pinned vippet revision is recorded in `vippet/.vippet-ref`.
