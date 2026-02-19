# Known Issues 

## Limited testing on EMT-S and EMT-D

- This release includes only limited testing on EMT‑S and EMT‑D, some behaviors may not yet be fully validated across all scenarios.
 
## RTSP stream not connecting
 
Symptoms:
- Stream shows "No streams active" or fails to add via UI.
- Video feed shows black screen or connection timeout.
 
Checks:
- Verify RTSP URL is reachable and credentials are correct.
- Ensure firewall allows RTSP port (default 554).
- Test with local file: `file:///path/to/video.mp4`.
 
## SSE events not updating
 
Symptoms:
- Dashboard shows stale data or "Last Sync" timestamp doesn't update.
- Alert results don't appear in real-time.
 
Checks:
- Check browser console (F12) for connection errors.
- Verify OVMS is running: `docker logs ovms-vlm | grep "Started REST"`.
- Test endpoint: `curl -N http://localhost:9000/events`.
- Ensure port 9000 isn't blocked by firewall.
 
## Port conflicts
 
If the dashboard or APIs are not reachable, check whether port 9000 is already in use and update the environment variable:
```bash
export PORT=9001
docker compose down && docker compose up -d
```
 
## VLM validation errors
 
Symptoms:
- Logs show "Validation failed" or "JSON parse error".
- Alerts show "NO" with reason "Validation error".
 
Checks:
- Verify model loaded: `docker logs ovms-vlm | grep "AVAILABLE"`.
- Simplify prompts to clear yes/no questions.
- Reduce concurrent alerts (max 4).
 
## Performance/throughput lower than expected
 
- Use faster model: `export OVMS_SOURCE_MODEL=OpenVINO/InternVL2-1B-int4-ov`.
- Reduce active streams or increase `ANALYSIS_INTERVAL`.
- Ensure hardware meets minimum requirements (see [system-requirements.md](system-requirements.md)).
 
## Model download fails
 
Symptoms:
- OVMS container exits or fails to start.
- Logs show Hugging Face download errors.
 
Checks:
- Check internet connectivity and proxy settings (`http_proxy`, `https_proxy`).
- Set `HF_TOKEN` environment variable for gated models.
- Ensure 2-4GB disk space available.
- Verify: `docker ps -a | grep ovms-init` shows "Exited (0)".
 