# Troubleshooting

## Stack Will Not Start

- Confirm the published host ports are free:

  ```bash
  ss -ltnp | grep -E "7860|8010|8011|8012|8020"
  ```

- Confirm Docker Compose can build:

  ```bash
  docker compose config
  docker compose build
  ```

- Tail individual services to find the first failure:

  ```bash
  docker compose logs -f audio-analyzer
  docker compose logs -f text-to-speech
  docker compose logs -f rag-service
  docker compose logs -f kiosk-core
  docker compose logs -f kiosk-ui
  ```

## First Startup Is Slow

This is expected. On first run each model-hosting service downloads or
exports model assets to its `models/` directory and Hugging Face cache.
Subsequent starts reuse the cached artifacts. The default
`audio-analyzer` healthcheck allows up to ~240 seconds for warmup; the
RAG LLM compile on GPU can also take a few minutes the first time.

## A `health` Endpoint Fails

- Run `docker compose ps` and check the `STATUS` column for `unhealthy`.
- If you are behind a corporate proxy, pass `--noproxy '*'` to `curl`
  when hitting `127.0.0.1`.
- Confirm the service container actually started:

  ```bash
  docker compose logs <service-name>
  ```

## Selected Device Is Not Used

The device field lives in the per-service pinned config (see
[Configuration](./get-started/configuration.md#inference-device)). If the device
does not appear in the logs:

- Check the value is supported for that model (e.g. `audio-analyzer`
  ASR supports `CPU` and `GPU` only).
- For `GPU`: confirm `/dev/dri` exists and the Intel OpenVINO GPU
  runtime is installed.
- Restart the affected service after the change:

  ```bash
  docker compose up -d --build --force-recreate <service-name>
  ```

- Confirm OpenVINO picked the device:

  ```bash
  docker compose logs <service-name> | grep -i -E "device|compiling|GPU|CPU"
  ```

## Permission Errors on Mounted Folders

Every container runs as UID/GID `1000:1000` (baked into each image).
Model files and caches for `audio-analyzer` and `text-to-speech` live
in Docker named volumes (`audio_analyzer_models`,
`audio_analyzer_cache`, `text_to_speech_models`, etc.) initialized with
that ownership, so the usual host-side ownership errors do not apply.
If you still see:

```
PermissionError: [Errno 13] Permission denied: '...'
```

on a path inside the container, a named volume was likely created
earlier with the wrong ownership (for example by an older root-only
run). Reset it:

```bash
docker compose down
docker volume rm \
  smart-kiosk-assistant_audio_analyzer_models \
  smart-kiosk-assistant_audio_analyzer_cache \
  smart-kiosk-assistant_text_to_speech_models \
  smart-kiosk-assistant_text_to_speech_cache
docker compose up -d
```
Replace `smart-kiosk-assistant_` with whatever Compose project prefix
`docker volume ls` shows on your host. Resetting a volume forces the
services to re-download model assets on next startup.

## Browser UI Does Not Capture Audio

- Confirm the browser granted microphone permission for
  `http://127.0.0.1:7860`. Reset the permission and reload if needed.
- Modern browsers restrict microphone access on insecure origins. Use
  `http://127.0.0.1` (loopback) or serve the UI behind HTTPS.
- Check the `kiosk-ui` logs for upload errors:

  ```bash
  docker compose logs -f kiosk-ui
  ```

## Answer Is Empty or Off-Topic

- Confirm the knowledge base was ingested. The Gradio UI exposes an
  ingestion panel; see also
  [rag-service/README.md](https://github.com/intel-retail/voice-enabled-interactions/blob/main/smart-kiosk-assistant/rag-service/README.md).
- Check `rag-service` logs for retrieval scores and reranker output.
- Try the same question from the API to rule out the UI:

  ```bash
  curl --noproxy '*' -X POST http://127.0.0.1:8020/api/v1/query \
    -H 'Content-Type: application/json' \
    -d '{"query":"What are the store hours?"}'
  ```

## TTS Plays No Audio in the Browser

- Confirm the session snapshot has non-empty `tts_audio_segments` and
  no `tts_errors`. See [API Reference](./api-reference.md).
- The `kiosk-core` container and the `kiosk-ui` container share the
  `generated_audio` Docker volume. If you removed the volume, recreate
  the stack:

  ```bash
  docker compose down
  docker compose up -d --build
  ```

## kiosk-core Cannot Reach a Downstream Service

The compose defaults wire `kiosk-core` and `kiosk-ui` to the internal
service names (`audio-analyzer`, `text-to-speech`, `rag-service`). If
you override these URLs for a host-run setup, confirm:

- The downstream service is reachable from `kiosk-core` (try `curl`
  against the override URL from inside the `kiosk-core` container or
  from the host).
- For host-run downstreams reached from a container, use
  `host.docker.internal` (see the alternative compose snippets in
  [Run With Docker Compose](./get-started/run-container.md)).

## See Also

- [Configuration](./get-started/configuration.md)
- [Get Started](./get-started.md)
- [Run On The Host](./get-started/run-standalone.md)
