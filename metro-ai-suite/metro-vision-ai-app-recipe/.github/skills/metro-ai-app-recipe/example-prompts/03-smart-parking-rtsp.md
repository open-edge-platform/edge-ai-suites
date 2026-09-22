# Smart-parking occupancy stack from RTSP cameras

Build an end-to-end stack in `./smart-parking-stack/` for the ITS vertical.
Object of interest: `vehicle`. Sources are four live RTSP camera URLs (not
sample videos). Node-RED rule: `count>10 in 30s per-source` to flag a full lot;
dashboard slug `smart-parking`. Publish detections to `object_detection_N/<pipeline>`,
alerts to `alerts/vehicle`, count to `stats/vehicle_count`. Stream the annotated
video over WebRTC (DLSPS WHIP → MediaMTX, Coturn ICE/TURN) and embed the WHEP
player as Grafana `<iframe>` panels at `/mediamtx/<peer-id>/`, ensure the
self-signed cert includes a SAN, and every `curl` uses `--noproxy '*'` and `--cacert` to trust the self-signed cert.
