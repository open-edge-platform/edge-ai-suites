# Run On The Host

Use this path to run `kiosk-core` and the Gradio UI directly on the host
instead of inside the top-level Compose stack. The microphone is still
captured by the browser and uploaded to `kiosk-core`.

## Clone

```bash
git clone https://github.com/intel-retail/voice-enabled-interactions.git
cd voice-enabled-interactions/smart-kiosk-assistant
```

## Start Downstream Services

Before starting `kiosk-core` and the UI on the host, make sure these downstream services are available:

- `audio-analyzer` at `http://127.0.0.1:8010/v1/audio/transcriptions`
- `text-to-speech` at `http://127.0.0.1:8011/v1/audio/speech`
- `rag-service` at `http://127.0.0.1:8020/api/v1/query`

The simplest way is to pull the prebuilt images for `audio-analyzer`
and `text-to-speech` from Docker Hub, build `rag-service` locally, and
run `kiosk-core` plus the UI on the host. The kiosk compose file in
`smart-kiosk-assistant/` already wires these three services together;
start only those three:

```bash
docker compose pull audio-analyzer text-to-speech
docker compose up -d audio-analyzer text-to-speech rag-service
```

`rag-service` builds locally because it ships in this repository under
[../rag-service/](https://github.com/intel-retail/voice-enabled-interactions/tree/main/smart-kiosk-assistant/rag-service).
The other two are pulled from `intel/audio-analyzer` and `intel/text-to-speech` on Docker Hub.

## Python Setup

From the `smart-kiosk-assistant/` directory:

```bash
sudo apt-get install -y --no-install-recommends libportaudio2

python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Start kiosk-core

Run the API on the host:

```bash
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8012
```

Default URLs used by `kiosk-core` in this host-run mode:

- `KIOSK_CORE_ANALYZER_URL=http://127.0.0.1:8010/v1/audio/transcriptions`
- `KIOSK_CORE_RAG_URL=http://127.0.0.1:8020/api/v1/query`
- `KIOSK_CORE_TTS_URL=http://127.0.0.1:8011/v1/audio/speech`

## Start The Gradio UI

In a second terminal, from the same `smart-kiosk-assistant/` directory:

```bash
source .venv/bin/activate
python gradio_app.py
```

Default UI URL:

```text
http://127.0.0.1:7860
```

Open that address in a browser, allow microphone access, and use the same browser-based voice flow as the Compose deployment.

## Verify

```bash
curl --noproxy '*' http://127.0.0.1:8012/health   # {"status":"ok"}
```

## Notes

- TTS audio clips are written under `generated_audio/` in the project directory.
- For endpoint details, see [API Reference](../api-reference.md).
