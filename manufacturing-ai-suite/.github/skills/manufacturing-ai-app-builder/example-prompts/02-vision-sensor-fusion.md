# Vision + sensor multimodal — weld defect detection

**User:**
> I want to catch defective welds — I have a camera on the weld and
> pressure/gas-flow sensors on the welder, and I only want an alert when
> both agree there's a problem.

Both signals must combine into one verdict, so it routes to
**`manufacturing-app-recipe`** (`{{DEPLOYMENT}}=multimodal`, `FUSION_MODE=AND`)
rather than a single-modality skill. The orchestrator confirms the video/CSV
input source and deployment target, then builds.

Output:
- `./weld-defect-stack/` Docker Compose solution: DLSPS (vision) + Telegraf/
  InfluxDB + Time Series Analytics (sensor) + Fusion Analytics
- A fused alert only when the camera and the sensor flag the same weld
- A Grafana dashboard at `https://localhost:3000` with the live video panel,
  sensor trend, and fused-verdict table
