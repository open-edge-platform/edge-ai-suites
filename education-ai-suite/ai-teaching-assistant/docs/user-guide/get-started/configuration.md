# Configuration

`kiosk-core` and `kiosk-ui` are configured through environment variables
(see [Environment Variables](#environment-variables)).

The three model-hosting services (`audio-analyzer`, `text-to-speech`,
`rag-service`) are configured through YAML files that the kiosk pins
and mounts into the containers. The most common changes are the
[model](#model-selection) and the [inference device](#inference-device).

## Model Selection

Each model-hosting service reads the model identifier from the same
pinned config file used for device selection:

| Service | File | Model fields |
|---|---|---|
| `audio-analyzer` | [`configs/audio-analyzer/config.yaml`](https://github.com/intel-retail/voice-enabled-interactions/blob/main/smart-kiosk-assistant/configs/audio-analyzer/config.yaml) | `models.asr.name` (e.g. `whisper-tiny`, `whisper-base`); `sentiment.model` (optional) |
| `text-to-speech` | [`configs/text-to-speech/config.yaml`](https://github.com/intel-retail/voice-enabled-interactions/blob/main/smart-kiosk-assistant/configs/text-to-speech/config.yaml) | `models.tts.name` (e.g. `microsoft/speecht5_tts`, Qwen-TTS variant); `model_variant` |
| `rag-service` | [`rag-service/config.yaml`](https://github.com/intel-retail/voice-enabled-interactions/blob/main/smart-kiosk-assistant/rag-service/config.yaml) | `models.llm.hf_id`, `models.embedding.hf_id`, `retrieval.reranker.hf_id`; per-model `weight_format` (`int4`, `int8`, `fp16`) |

Use Hugging Face IDs where the field name is `hf_id`. Models are
downloaded and exported on first start into the per-service `models/`
directory; subsequent starts reuse the cache.

### Supported / validated models

The kiosk ships with the following defaults. These are the models the
stack has been validated with — they are the recommended starting point.
The **Devices** column lists the supported inference devices for each:

| Service | Field | Default (validated) | Other examples | Devices |
|---|---|---|---|---|
| `audio-analyzer` ASR | `models.asr.name` | `whisper-base` | `whisper-tiny`, `whisper-small`, `whisper-medium`, `whisper-large` | `CPU`, `GPU` (`GPU` requires `provider: openvino`) |
| `audio-analyzer` sentiment | `sentiment.model` | `speechbrain/emotion-recognition-wav2vec2-IEMOCAP` | other SpeechBrain emotion-recognition models | `CPU`, `GPU` (disabled by default) |
| `text-to-speech` | `models.tts.name` | `microsoft/speecht5_tts` (SpeechT5) | `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` (Qwen-TTS) | `CPU`, `GPU` (`int4` on iGPU produces noise; use `fp16` or `int8` on GPU) |
| `rag-service` LLM | `models.llm.hf_id` | `Qwen/Qwen3-4B-Instruct-2507` | other OpenVINO-exportable instruct LLMs | `CPU`, `GPU` (`GPU` recommended for acceptable latency) |
| `rag-service` embedding | `models.embedding.hf_id` | `BAAI/bge-large-en-v1.5` | `BAAI/bge-base-en-v1.5`, `BAAI/bge-small-en-v1.5` | `CPU`, `GPU` (`CPU` is usually fast enough) |
| `rag-service` reranker | `retrieval.reranker.hf_id` | `BAAI/bge-reranker-base` | `BAAI/bge-reranker-large` | `CPU`, `GPU` (optional) |

> [!IMPORTANT]
> **Changing models is at your own discretion.** The defaults above are
> the only combinations validated with this stack. Configuring models,
> variants, devices, or precisions other than the defaults may negatively
> affect the functionality, accuracy, latency, or stability of the
> application. You are responsible for ensuring the configuration you
> choose is correct and works for your use case — make changes only if you
> understand the implications.
>
> In particular:
> - Some models do not function properly at aggressive quantization. If a
>   model produces garbled, empty, or low-quality output at `int4`, switch
>   that model's `weight_format`/`dtype` to `int8` or `fp16`.
> - A model must be exportable to OpenVINO IR for the OpenVINO backend; not
>   every Hugging Face model is supported.
> - Larger models increase first-run download/export time, memory use, and
>   per-request latency, and may not fit on the selected device.
> - After any change, restart the affected service and verify it loads and
>   responds correctly before relying on it.

## Inference Device

Each model-hosting service reads its device from a pinned config file:

| Service | File | Fields |
|---|---|---|
| `audio-analyzer` | [`configs/audio-analyzer/config.yaml`](https://github.com/intel-retail/voice-enabled-interactions/blob/main/smart-kiosk-assistant/configs/audio-analyzer/config.yaml) | `models.asr.device`, `sentiment.device` |
| `text-to-speech` | [`configs/text-to-speech/config.yaml`](https://github.com/intel-retail/voice-enabled-interactions/blob/main/smart-kiosk-assistant/configs/text-to-speech/config.yaml) | `models.tts.device` |
| `rag-service` | [`rag-service/config.yaml`](https://github.com/intel-retail/voice-enabled-interactions/blob/main/smart-kiosk-assistant/rag-service/config.yaml) | `models.llm.device`, `models.embedding.device`, `retrieval.reranker.device` |

The supported devices for each model are listed in the
[Supported / validated models](#supported--validated-models) table above.

Use uppercase device names (`CPU`, `GPU`). `rag-service` expects
them as quoted strings; `audio-analyzer` and `text-to-speech` unquoted.

After editing, restart the affected service and confirm OpenVINO picked
the device:

```bash
docker compose up -d --build --force-recreate <service-name>
docker compose logs <service-name> | grep -i -E "device|compiling|GPU|CPU"
```

OpenVINO prints a `Compiling model on <DEVICE>` line on first load.

> GPU execution is delegated to the OpenVINO backend used by each
> service. Whether a given model actually runs on GPU and how it
> performs depends on the OpenVINO version and operator coverage for
> that model.

## Environment Variables

kiosk-core has no config file. All settings are controlled through environment variables.

### kiosk-core API (`main:app`)

| Variable | Default | Description |
|---|---|---|
| `KIOSK_CORE_ANALYZER_URL` | `http://127.0.0.1:8010/v1/audio/transcriptions` | audio-analyzer transcription endpoint |
| `KIOSK_CORE_RAG_URL` | `http://127.0.0.1:8020/api/v1/query` | RAG query endpoint |
| `KIOSK_CORE_TTS_URL` | `http://127.0.0.1:8011/v1/audio/speech` | TTS speech synthesis endpoint |
| `KIOSK_CORE_TTS_MODEL` | `qwen-tts` | Model name sent to the TTS service |
| `KIOSK_CORE_TTS_VOICE` | *(unset)* | Voice name sent to the TTS service |
| `KIOSK_CORE_TTS_LANGUAGE` | `English` | Language sent to the TTS service |
| `KIOSK_CORE_TTS_INSTRUCTIONS` | *(unset)* | Optional style instructions for TTS |
| `KIOSK_CORE_SAMPLE_RATE` | `16000` | Default audio sample rate in Hz |
| `KIOSK_CORE_CHUNK_SECONDS` | `4.0` | Length of each audio chunk sent to audio-analyzer |
| `KIOSK_CORE_SILENCE_TIMEOUT_SECONDS` | `1.5` | Silence duration after speech that ends a session |
| `KIOSK_CORE_MAX_SESSION_SECONDS` | `20.0` | Hard cap on session duration |
| `KIOSK_CORE_SILENCE_THRESHOLD` | `900` | RMS threshold below which audio is treated as silence |
| `KIOSK_CORE_BLOCK_DURATION_SECONDS` | `0.1` | PortAudio capture block size |
| `KIOSK_CORE_PREROLL_SECONDS` | `0.3` | Audio buffered before speech starts |
| `KIOSK_CORE_HTTP_TIMEOUT_SECONDS` | `120.0` | HTTP client timeout for downstream calls |

### Gradio UI (`gradio_app.py`)

| Variable | Default | Description |
|---|---|---|
| `KIOSK_CORE_UI_BASE_URL` | `http://127.0.0.1:8012` | Base URL of the kiosk-core API |
| `KIOSK_CORE_UI_ANALYZER_URL` | `http://127.0.0.1:8010/v1/audio/transcriptions` | Passed to start-file sessions as `analyzer_url` |
| `KIOSK_CORE_UI_RAG_URL` | `http://127.0.0.1:8020/api/v1/query` | Passed to start-file sessions as `rag_url` |
| `KIOSK_CORE_UI_TTS_URL` | `http://127.0.0.1:8011/v1/audio/speech` | Passed to start-file sessions as `tts_url` |
| `KIOSK_CORE_UI_TIMEOUT_SECONDS` | `120.0` | HTTP client timeout in the UI |
| `KIOSK_CORE_UI_POLL_INTERVAL_SECONDS` | `0.35` | How often the UI polls for session state updates |

## Compose Defaults

When running with the top-level [docker-compose.yml](https://github.com/intel-retail/voice-enabled-interactions/blob/main/smart-kiosk-assistant/docker-compose.yml), the defaults are wired to the internal Compose network:

- `KIOSK_CORE_ANALYZER_URL=http://audio-analyzer:8010/v1/audio/transcriptions`
- `KIOSK_CORE_RAG_URL=http://rag-service:8020/api/v1/query`
- `KIOSK_CORE_TTS_URL=http://text-to-speech:8011/v1/audio/speech`
- `KIOSK_CORE_UI_BASE_URL=http://kiosk-core:8012`

Most deployments should leave these values unchanged. Override them only when `kiosk-core` or `kiosk-ui` must call services outside the local Compose stack.

## Session Parameters

Session parameters (chunk duration, silence threshold, etc.) can also be provided per-request in the POST body for `/api/v1/sessions/start` and `/api/v1/sessions/start-file`. Per-request values take precedence over the environment variable defaults.
