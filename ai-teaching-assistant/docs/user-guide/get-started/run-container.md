# Run With Docker Compose

`docker compose up` starts `audio-analyzer`, `text-to-speech`,
`rag-service`, `kiosk-core` (REST API), and `kiosk-ui` (Gradio interface)
as containers, using the prebuilt images published on Docker Hub.

Microphone audio is captured by the browser and uploaded to `kiosk-core`
as a WAV file. No host audio device is passed into the containers.

To rebuild the images from source instead of pulling, see
[Build from Source](./build-from-source.md). To run `kiosk-core` and
the UI directly on the host, see [Run On the Host](./run-standalone.md).

## Clone

```bash
git clone https://github.com/intel-retail/voice-enabled-interactions.git
cd voice-enabled-interactions/smart-kiosk-assistant
```

## Pull And Start

From `smart-kiosk-assistant/`:

```bash
docker compose pull
docker compose up -d
```

`docker compose pull` fetches all five images from Docker Hub:

- `intel/audio-analyzer:${RELEASE_TAG}`
- `intel/text-to-speech:${RELEASE_TAG}`
- `intel/rag-service:${RELEASE_TAG}`
- `intel/kiosk-core:${RELEASE_TAG}`
- `intel/kiosk-ui:${RELEASE_TAG}`

`REGISTRY` and `RELEASE_TAG` are read from [.env](https://github.com/intel-retail/voice-enabled-interactions/blob/main/smart-kiosk-assistant/.env)
(defaults: `REGISTRY=intel`, committed `RELEASE_TAG` pins the current release).

This starts five containers:

| Container | Port | Purpose |
|---|---|---|
| `audio-analyzer` | 8010 | Speech-to-text |
| `text-to-speech` | 8011 | Speech synthesis |
| `rag-service` | 8020 | Knowledge-base retrieval |
| `kiosk-core` | 8012 | FastAPI session API |
| `kiosk-ui` | 7860 | Gradio voice UI |

Containers run as non-root; every image is built with UID/GID
`1000:1000` and the named volumes are initialized with that ownership,
so no host UID/GID configuration is required.

## Verify

```bash
docker compose ps
curl --noproxy '*' http://127.0.0.1:8012/health   # {"status":"ok"}
```

Open `http://127.0.0.1:7860` in a browser, click the microphone, and
speak your question.

## Logs

```bash
docker compose logs -f kiosk-core
docker compose logs -f kiosk-ui
```

## Restart / Stop

```bash
docker compose restart            # after env var change
docker compose pull && docker compose up -d   # after a new release tag
docker compose down               # teardown
```

## Notes

- The default Compose wiring connects `kiosk-core` and `kiosk-ui` to the
  internal `audio-analyzer`, `rag-service`, and `text-to-speech`
  containers. Override these URLs only when this stack must call
  services outside the local Compose network.
- See [Configuration](./configuration.md) for environment variables,
  model selection, and inference device, and
  [API Reference](../api-reference.md) for endpoint details.
