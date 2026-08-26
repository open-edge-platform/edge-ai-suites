# Vision detection — camera feeds → end-to-end analytics stack

**User (business objective):**
> I want to know whenever a person walks into my warehouse loading bay after
> hours, from my existing cameras, and see it on a dashboard.

**Orchestrator (Step 1 — business Q&A, batched):**
1. Outcome — alert on a person present in a monitored area after hours? [yes]
2. Inputs — an ONVIF camera [default], live RTSP/USB cameras, or looping sample
   video for a demo? [ONVIF]
3. Deployment — quick local demo, single-host Docker solution, or Kubernetes?
   [single-host Docker]
4. Hardware — Intel GPU (default), or Intel CPU/NPU? [Intel GPU]
5. Do you need a live annotated video wall + alert dashboard? [yes]

**Discovery (Step 2):** verb *detect* + object *person* + object *camera feeds* +
*dashboard* → **`metro-ai-apps-recipe`** (this repo; end-to-end DLSPS + WebRTC +
Node-RED + Grafana stack). No supporting skill needed (built-in person model).

**Plan (Step 4 — presented, awaits confirmation):**
- Deliverable: `./person-detect-stack/` Docker Compose solution; Grafana at
  `https://localhost/grafana` with live annotated WebRTC panels + after-hours
  person alerts.
- Skill: `metro-ai-apps-recipe` (already in this repo — no install).
- Inferred technology (decisions, not questions): YOLO-family person detector,
  Intel GPU, INT8, one ONVIF camera source, Node-RED rule `count>0 in 10s` per
  source, MQTT topics `object_detection_N/<pipeline>`, alerts `alerts/person`.
- Requirements: Docker + Compose v2; ports 80/443 and 3478/udp free.

**Build (Step 5, after "go"):** delegate to `metro-ai-apps-recipe`, passing the
inferred `{{OBJECT}}=person`, `{{STACK_DIR}}=person-detect-stack`, rule, and
topics. Verify against that skill's completion criteria, then tell the user how
to open the dashboard.
