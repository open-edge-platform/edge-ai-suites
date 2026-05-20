# Handheld Multi-Modal

Full-stack AI inference and observability platform for handheld deployment scenarios, optimized for Intel edge hardware.

## Applications

| Application | Location | Description |
|-------------|----------|-------------|
| OpenVINO Model Server (OVMS) | `apps/LLM-OpenWebUI/` | Serves OpenVINO-optimized LLMs via an OpenAI-compatible REST API |
| Open WebUI | `apps/LLM-OpenWebUI/` | Web-based chat interface connected to OVMS |
| Whisper STT | `apps/speech-to-text/` | Speech-to-text transcription service |
| Grafana | `apps/grafana/` | Metrics dashboards consuming data from the running services |
| NGINX HTTPS proxy | `apps/nginx/` | Reverse proxy providing HTTPS access — required for browser microphone use |
