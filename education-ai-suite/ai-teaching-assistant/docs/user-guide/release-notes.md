# Release Notes: AI Teaching Assistant

## Version 2026.2.0

**Release Date**: September 9, 2026

Initial AI Teaching Assistant documentation baseline aligned with the current
Windows-native runtime architecture.

**Features**:

- React-based browser UI served by `ata_ui_server.py`
- `kiosk-core` streaming session orchestration API
- Local ASR (`audio-analyzer`), RAG (`rag-service`), and TTS (`text-to-speech`)
- Multi-file knowledge-base ingestion support (`.txt`, `.md`, `.docx`, `.pdf`)
- Metrics integration via `metrics-collector`
- Windows launcher workflow (`setup_windows.ps1`, `start_ata.ps1`, `stop_ata.ps1`)

**Documentation updates**:

- Removed outdated container/build-path documentation from this guide
- Removed repository clone instructions that pointed to upstream Voice Enabled Interactions (VEI)
- Updated architecture, API, configuration, and troubleshooting pages to match
  `ai-teaching-assistant` as shipped in `edge-ai-suites`
