# Surface-defect stack with a custom OpenVINO IR model

Build an end-to-end stack in `./defect-detect-stack/` for the manufacturing
vertical. Object of interest: `defect`. I have my own OpenVINO IR detector
(custom `.xml`/`.bin`) rather than a stock model — register it with DL Streamer
Pipeline Server and wire the class filter for my defect class IDs in Node-RED.
Run on `AUTO` device selection, publish detections to
`object_detection_N/<pipeline>`, alert on `count>0 in 5s per-source`, and stream
the annotated frames as HLS into Grafana. Enforce the parameter validation
(`validate_env.sh`) before install and confirm the watchdog respawns completed
file-source pipelines.
