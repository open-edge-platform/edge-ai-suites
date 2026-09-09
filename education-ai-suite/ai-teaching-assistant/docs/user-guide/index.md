# AI Teaching Assistant

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/education-ai-suite/ai-teaching-assistant">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/education-ai-suite/ai-teaching-assistant/README.md">
     Readme
  </a>
</div>
hide_directive-->

An intelligent voice-enabled teaching assistant for educational environments. This application provides interactive Q&A capabilities powered by local AI models, allowing users to ask questions about uploaded course materials and receive instant, grounded answers via voice and text.

All inference runs locally on Intel CPU/GPU via OpenVINO™ — **no cloud dependencies, no external APIs**.

## Key Features

- **Voice-First Interface** — Ask questions naturally using your microphone
- **Multi-Format Support** — Ingest `.txt`, `.md`, `.docx`, and `.pdf` course materials
- **Local AI Processing** — All speech-to-text, retrieval, and synthesis run on-device
- **Real-Time Responses** — Streamed answers with synthesized voice output
- **Persistent Knowledge Base** — Course materials persist across sessions

## Services

| Service                    | Port | Role                                                 |
| -------------------------- | ---- | ---------------------------------------------------- |
| `audio-analyzer`           | 8010 | Speech-to-text (Whisper)                             |
| `text-to-speech`           | 8011 | Speech synthesis (SpeechT5 / Qwen-TTS)               |
| `rag-service`              | 8020 | Knowledge ingestion & retrieval-augmented generation |
| `kiosk-core`               | 8012 | Session management & service orchestration           |
| `ai-teaching-assistant ui` | 7860 | React browser interface                              |

Model inference is distributed across `audio-analyzer`, `text-to-speech`, and `rag-service`. The `kiosk-core` and `ai-teaching-assistant ui` services handle I/O and orchestration only.

## Quick Start

For full setup steps, use [Get Started](./get-started.md).

> **Note:** If PowerShell blocks local scripts on your machine, run this command in the current terminal session before setup:
>
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```

High-level flow:

```powershell
git clone --filter=blob:none --sparse https://github.com/open-edge-platform/edge-ai-suites.git -b main;
cd edge-ai-suites;
git sparse-checkout set education-ai-suite/ai-teaching-assistant;
cd education-ai-suite/ai-teaching-assistant;
.\setup_windows.ps1;
.\start_ata.ps1
```

Open `http://127.0.0.1:7860` in your browser.

## Next Steps

- [Get Started](./get-started.md) — Full setup guide
- [Application Flow](./application-flow.md) — UI walkthrough and element reference
- [How It Works](./how-it-works.md) — Architecture and data flow
- [System Requirements](./get-started/system-requirements.md) — Hardware and OS requirements
- [Configuration](./get-started/configuration.md) — Model selection and tuning
- [Troubleshooting](./troubleshooting.md) — Common issues and solutions
- [Release Notes](./release-notes.md) — Version history

<!--hide_directive
:::{toctree}
:hidden:

./get-started.md
./application-flow.md
./how-it-works.md
./api-reference.md
./troubleshooting.md
Release Notes <./release-notes.md>

:::
hide_directive-->
