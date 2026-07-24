# Smart Kiosk Assistant

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/intel-retail/voice-enabled-interactions/tree/main/smart-kiosk-assistant">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/intel-retail/voice-enabled-interactions/blob/main/smart-kiosk-assistant/README.md">
     Readme
  </a>
</div>
hide_directive-->

This application is part of the Voice Enabled Interactions reference architecture for retail.

Smart Kiosk Assistant is a voice-first, retrieval-augmented kiosk stack
for retail, Quick Service Restaurant (QSR), and similar customer-facing deployments. The browser
captures microphone audio, the stack transcribes it, retrieves a grounded
answer from a local knowledge base, and plays a synthesized reply. All
inference runs locally on Intel CPU or GPU via OpenVINO.

## Services

| Service          | Port | Role                                           |
| ---------------- | ---- | ---------------------------------------------- |
| `audio-analyzer` | 8010 | Speech-to-text (Whisper)                       |
| `text-to-speech` | 8011 | Speech synthesis (SpeechT5 / Qwen-TTS)         |
| `rag-service`    | 8020 | Knowledge-base retrieval and answer generation |
| `kiosk-core`     | 8012 | FastAPI session orchestrator                   |
| `kiosk-ui`       | 7860 | Gradio browser interface                       |

`audio-analyzer`, `text-to-speech`, and `rag-service` host the inference
models. `kiosk-core` and `kiosk-ui` are I/O-only.

## Next Steps

- [Get Started](./get-started.md)
- [How It Works](./how-it-works.md)
- [Release Notes](./release-notes.md)

<!--hide_directive
:::{toctree}
:hidden:

./get-started.md
./how-it-works.md
./api-reference.md
./troubleshooting.md
Release Notes <./release-notes.md>

:::
hide_directive-->
