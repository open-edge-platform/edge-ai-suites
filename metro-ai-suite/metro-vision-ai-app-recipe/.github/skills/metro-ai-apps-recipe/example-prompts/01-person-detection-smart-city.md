# Person-counting stack for a smart-city camera feed

Build a full end-to-end computer-vision analytics stack in `./person-detect-stack/`
using the metro-ai-apps-recipe. Vertical: smart city. Object of interest:
`person`. Use a YOLO-family person detector on CPU, four looping sample-video
sources, and a Node-RED rule that alerts when `count>2 in 10s` per source.
Publish detections to `object_detection_N/<pipeline>`, alerts to
`alerts/person`, and a scalar count to `stats/person_count`. Produce the DLSPS
config, Mosquitto, Node-RED flow, Nginx TLS proxy, Grafana dashboard, and pytest
suite, then verify against the completion criteria.
