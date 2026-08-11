# Configuration References

This folder stores reference configuration for the upstream services used by
AI Teaching Assistant:

- [configs/audio-analyzer/config.yaml](configs/audio-analyzer/config.yaml)
- [configs/text-to-speech/config.yaml](configs/text-to-speech/config.yaml)

## Important Runtime Note

In this Windows-native application flow, services run directly from the
submodule source trees. The active runtime configs are read from:

- [edge-ai-libraries/microservices/audio-analyzer/config.yaml](edge-ai-libraries/microservices/audio-analyzer/config.yaml)
- [edge-ai-libraries/microservices/text-to-speech/config.yaml](edge-ai-libraries/microservices/text-to-speech/config.yaml)
- [voice-enabled-interactions/smart-kiosk-assistant/rag-service/config.yaml](voice-enabled-interactions/smart-kiosk-assistant/rag-service/config.yaml)

If you change values here under `configs/`, copy those values to the runtime
config files above before restarting services.

## Why Keep This Folder

- Maintains a project-owned baseline for ASR and TTS behavior.
- Helps track intentional config choices separately from upstream defaults.
- Makes it easier to compare and review config changes.
