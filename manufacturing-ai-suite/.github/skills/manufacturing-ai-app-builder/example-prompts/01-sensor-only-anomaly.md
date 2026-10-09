# Sensor-only anomaly detection — pump vibration monitoring

**User:**
> Alert me when one of my pumps is about to fail based on its vibration
> sensor readings, and show it on a dashboard.

Only a sensor feeds this decision, no camera, so it routes to
**`manufacturing-app-recipe`** (`{{DEPLOYMENT}}=ts`). The orchestrator just
confirms the ingestion source (sample dataset vs. a real OPC-UA/MQTT feed)
and that a dashboard is wanted, then builds.

Output:
- A new `apps/pump-vibration-monitor/` sample app with a pretrained
  vibration-anomaly UDF
- An MQTT alert on `alerts/pump_vibration` when amplitude is anomalous
- A Grafana dashboard at `https://localhost:3000` showing the live trend
