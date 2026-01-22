# Known Issues

## WebRTC connectivity issues

Symptoms:
- Black video, no stream, or connection failures in the dashboard.

Checks:
- Verify `HOST_IP` in `.env` is reachable from the browser client.
- Confirm firewall rules allow the configured ports.

## No models in dropdown

Symptoms:
- Model list is empty in the UI.

Checks:
- Ensure `ov_models/` contains at least one model directory with OpenVINO IR files.
- If you downloaded models, re-run the stack so the service rescans.

## Pipeline server unreachable

Symptoms:
- Starting a run fails; backend reports it cannot reach the pipeline server.

Checks:
- Ensure the `dlstreamer-pipeline-server` service is running.
- Verify `PIPELINE_SERVER_URL` (defaults to `http://dlstreamer-pipeline-server:8080`).

## Port conflicts

If the dashboard or APIs are not reachable, check whether the ports are already in use and update the `.env` values (for example `DASHBOARD_PORT`).

## Performance/throughput lower than expected

- Larger VLMs require more compute and memory; try a smaller model.
- Reduce `max_tokens`.
- Ensure hardware acceleration and drivers are installed if using GPU.

## Gemma model not working in GPU

- Gemma model is not working on GPU. Only working on CPU.