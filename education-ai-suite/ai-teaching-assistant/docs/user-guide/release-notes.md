# Release Notes

## 2026.1.0

Initial AI Teaching Assistant documentation baseline aligned to the current
Windows-native runtime architecture.

Highlights:
- React-based browser UI served by `ata_ui_server.py`
- `kiosk-core` streaming session orchestration API
- Local ASR (`audio-analyzer`), RAG (`rag-service`), and TTS (`text-to-speech`)
- Multi-file knowledge-base ingestion support (`.txt`, `.md`, `.docx`, `.pdf`)
- Metrics integration via `metrics-collector`
- Windows launcher workflow (`setup_windows.ps1`, `start_ata.ps1`, `stop_ata.ps1`)

Documentation updates in this release:
- Removed outdated container/build-path docs from this app guide
- Removed repository clone guidance that pointed to upstream VEI directly
- Updated architecture, API, configuration, and troubleshooting pages to match
  `ai-teaching-assistant` as shipped in `edge-ai-suites`
