# Known Issues

## Limited testing on EMT-S and EMT-D

- This release includes only limited testing on EMT‑S and EMT‑D. Some behaviors may not yet be fully validated across all scenarios.

## ADK mode requires LLM service to be reachable

`USE_ADK=true` is the **default** and connects to the `ovms-llm` service on every
alert dispatch. If that container is not running or unreachable:

- Ensure the `ovms-llm` service has started: `docker logs ovms-llm | grep AVAILABLE`
- Set `USE_ADK=false` to fall back to rule-based dispatch (no external LLM needed).

## LLM tool-calling support varies by model

Not all OVMS-served text models implement robust OpenAI-style function-calling.
The agent automatically falls back to JSON text parsing in that case, but very
small models (< 3B parameters) may produce unpredictable output.

Recommended models for reliable tool-calling: `Phi-4-mini-instruct-int4-ov`,
`Phi-3.5-mini-instruct`, `Mistral-7B-Instruct` (OV-converted variants).

If neither strategy returns valid tool names, rule-based dispatch is used as a
final fallback — alerts continue to function.

## Snapshot directory not writable

If `capture_snapshot` fails with a permission error, the container’s
`/app/snapshots` directory may not be writable by `appuser`:

```bash
docker exec live-video-alert-agent ls -la /app/snapshots
```

If using a host-bind mount instead of the `snapshots` named volume, ensure the
host directory is owned by UID 1000.

## RTSP stream not connecting

Symptoms:

- Stream shows "No streams active" or fails to add via UI.
- Video feed shows a black screen or connection timeout.

Checks:

- Verify RTSP URL is reachable and credentials are correct.
- Ensure firewall allows RTSP port (default 554).
- Test with local file: `file:///path/to/video.mp4`.

## SSE events not updating

Symptoms:

- Dashboard shows stale data, or the "Last Sync" timestamp doesn't update.
- Alert results don't appear in real-time.

Checks:

- Check browser console (F12) for connection errors.
- Refresh the browser window.
- Verify that OVMS is running: `docker logs ovms-vlm | grep "Started REST"`.
- Test endpoint: `curl -N http://localhost:9000/events`.
- Ensure port 9000 isn't blocked by firewall.

## Port conflicts

If the dashboard or APIs are not reachable, check whether port 9000 is already in use. Update the port in the docker compose yaml.

```bash
docker compose down && docker compose up -d
```

## VLM validation errors

Symptoms:

- Logs show "Validation failed" or "JSON parse error".
- Alerts show "NO" with reason "Validation error".

Checks:

- Verify model loaded: `docker logs ovms-vlm | grep "AVAILABLE"`.
- Simplify prompts to ask clear yes/no questions.
- Reduce concurrent alerts (max 4) if batching issues occur.

## MCP server connection failures

Symptoms:

- Logs show `[mcp/{server}] Connection failed` at startup.
- `GET /mcp/status` shows `connected: false`.

Checks:

- Verify the MCP server is running and reachable from the container.
- Check `url` in `resources/mcp_servers.json` is correct.
- Set `enabled: false` for an MCP server entry to disable it without removing it.
- Use `POST /mcp/reload` to reconnect without restarting the application.

## Performance/throughput lower than expected

- Reduce active streams or increase `ANALYSIS_INTERVAL`.
- Ensure hardware meets minimum requirements (see [system-requirements.md](./get-started/system-requirements.md)).

## Model download fails

Symptoms:

- The OVMS container exits or fails to start.
- Logs show Hugging Face download errors.

Checks:

- Check internet connectivity and proxy settings (`http_proxy`, `https_proxy`).
- Set the `HF_TOKEN` environment variable for gated models.
- Ensure 2-4GB disk space available.
- Verify: `docker ps -a | grep ovms-init` shows "Exited (0)".
