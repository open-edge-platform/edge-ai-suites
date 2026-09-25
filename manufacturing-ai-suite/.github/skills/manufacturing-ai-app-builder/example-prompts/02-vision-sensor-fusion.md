# Vision + sensor fusion — weld defect detection

**User (business objective):**
> I want to catch defective welds on my production line — I have a camera
> looking at the weld and pressure/gas-flow sensors on the welder, and I want
> one alert only when both point to a problem.

**Orchestrator (Step 1 — business Q&A, batched):**
1. Outcome — one fused defect alert combining camera + sensor evidence? [yes]
2. What feeds this — a camera, sensors, or both together? [both — camera +
   pressure/gas-flow, correlated]
3. Inputs — camera: sample weld video for a demo, or a real RTSP feed?
   [sample video]; sensors: real OPC-UA/MQTT feed, or looping sample CSV?
   [sample CSV]
4. Deployment — quick local demo, single-host Docker solution, or
   Kubernetes? [single-host Docker]
5. Fuse with AND (both must agree) or OR (either is enough)? [AND]

**Discovery (Step 2):** "what feeds this" = both, correlated into one verdict
→ **`manufacturing-multimodal-app-recipe`** (this workspace; DLSPS + Telegraf/
InfluxDB + Time Series Analytics + Fusion Analytics + Grafana). This is
**not** routed to `manufacturing-timeseries-app-recipe` or `metro-ai-app-recipe`
alone, because the business requirement is explicitly a **combined** verdict.

**Plan (Step 4 — presented, awaits confirmation):**
- Deliverable: `./weld-defect-stack/` Docker Compose solution; Grafana at
  `https://localhost:3000` with a live annotated WebRTC panel, sensor trend,
  and fused-verdict table.
- Skill: `manufacturing-multimodal-app-recipe` (this workspace — no install).
- Supporting: `dlsps-user` for the vision pipeline operational details,
  `time-series-analytics-user` for the sensor UDF pattern.
- Inferred technology (decisions, not questions): weld-defect classifier on
  CPU, `FUSION_MODE=AND`, 50 ms timestamp tolerance, MQTT topics
  `vision_weld_defect_classification` / `ts_weld_anomaly_detection` /
  `fusion/anomaly_detection_results`.
- Requirements: Docker + Compose v2; Nginx/Coturn ports free.
- On Kubernetes → the reference app's own `helm/` chart deploys the same
  stack.

**Build (Step 5, after "go"):** delegate to `manufacturing-multimodal-app-recipe`,
passing the inferred `{{OBJECT}}=weld_defect`, `{{FUSION_MODE}}=AND`, and
topics; verify against the recipe's own completion criteria (including the
fused-verdict MQTT proof), then tell the user how to open the dashboard.
