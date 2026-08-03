# Smart-parking occupancy stack from RTSP cameras

Build an end-to-end stack in `./smart-parking-stack/` for the ITS vertical.
Object of interest: `vehicle`. Sources are four live RTSP camera URLs (not
sample videos). Node-RED rule: `count>10 in 30s per-source` to flag a full lot;
dashboard slug `smart-parking`. Publish detections to `object_detection_N/<pipeline>`,
alerts to `alerts/vehicle`, count to `stats/vehicle_count`. Ensure the HLS video
panels embed via iframe + `player.html` with locally bundled hls.js, the
self-signed cert includes a SAN, and every `curl` uses `--noproxy '*' -k`.
