# Sensor-only anomaly detection — pump vibration monitoring

**User (business objective):**
> I want to know when one of my pumps is about to fail, based on its
> vibration sensor readings, and see it on a dashboard.

**Orchestrator (Step 1 — business Q&A, batched):**
1. Outcome — alert before a pump failure, based on vibration anomalies? [yes]
2. What feeds this — a camera, the vibration sensor, or both together?
   [vibration sensor only]
3. Inputs — a real OPC-UA/MQTT feed from the pump's sensor, or a looping
   sample dataset for a demo? [sample dataset]
4. Deployment — quick local demo, single-host Docker solution, or
   Kubernetes? [single-host Docker]
5. Do you need a live sensor-trend + anomaly dashboard? [yes]

**Discovery (Step 2):** "what feeds this" = sensor only, full dashboard
requested → **`manufacturing-timeseries-app-recipe`** (this workspace;
Telegraf/InfluxDB + Time Series Analytics Microservice + Grafana, scaffolded
as a new `apps/pump-vibration-monitor/` sample app). No vision component, so
`manufacturing-multimodal-app-recipe` does not apply.

**Plan (Step 4 — presented, awaits confirmation):**
- Deliverable: a new `apps/pump-vibration-monitor/` folder registered in the
  Time Series AI Stack's `Makefile`; Grafana at
  `https://localhost:3000` showing vibration trend + anomaly alerts.
- Skill: `manufacturing-timeseries-app-recipe` (this workspace — no install).
- Supporting: `time-series-analytics-user` for the actual UDF/TICKscript
  pattern (a pretrained rolling-anomaly model on vibration amplitude).
- Inferred technology (decisions, not questions): OPC-UA ingestion via the
  bundled simulator, MQTT alert channel on `alerts/pump_vibration`, streaming
  (non-batch) UDF, single stream.
- Requirements: Docker + Compose v2; port `3000` free.
- On Kubernetes → the reference app's own `helm/` chart deploys the same
  stack.

**Build (Step 5, after "go"):** delegate to `manufacturing-timeseries-app-recipe`,
passing the inferred `{{APP_NAME}}=pump-vibration-monitor`, ingestion
transport, and alert channel; it in turn delegates the UDF authoring to
`time-series-analytics-user`. Verify against the recipe's own completion
criteria, then tell the user how to run `make up_opcua_ingestion
app=pump-vibration-monitor` and open the dashboard.
