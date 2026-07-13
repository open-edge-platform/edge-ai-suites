# Kiosk service configs

This folder holds **kiosk-pinned** configuration for the upstream services we
spin up from `docker-compose.yml`:

- `audio-analyzer/config.yaml` — mounted into the `audio-analyzer`
  container at `/app/audio_analyzer/config.yaml`. Pins the ASR model,
  device, denoise/chunking settings, allowed audio formats, and sentiment
  options.
- `text-to-speech/config.yaml` — mounted into the `text-to-speech`
  container at `/app/text-to-speech/config.yaml`. Pins the TTS model,
  voice, language, device, dtype, and output format.

> Note: The `rag-service` reads its settings directly from its own
> `rag-service/config.yaml` (no override layer), so it does not need the
> `configs/` indirection — only the two services that come from the
> upstream [edge-ai-libraries](https://github.com/open-edge-platform/edge-ai-libraries) project do.

## Why this exists

Both services are published as `intel/audio-analyzer` and
`intel/text-to-speech` on Docker Hub and ship their own default
`config.yaml`. Those defaults can change over time, and the
kiosk needs reproducible behaviour (specific ASR model, specific TTS voice,
denoise off, etc.).

By keeping a pinned copy here and mounting it as the service config, we get:

1. The kiosk always boots the exact service configuration it was tested with,
   regardless of upstream image updates.
2. **No fork / no patches** of the upstream services — they're consumed as-is.
3. Anyone tweaking kiosk behaviour edits files in this folder, not in the
   upstream repository.

## How it works

`docker-compose.yml` mounts these files read-only into each container as
`config.yaml`, so the upstream services read them as their primary
configuration with no service code changes.

## Updating

1. Edit the YAML here.
2. `docker compose up -d --build --force-recreate audio-analyzer` (or
   `text-to-speech`).
3. The service restarts with the new pinned config.
