# Vision only — camera-based PCB defect detection

**User:**
> I want to spot defective solder joints on PCBs from my inspection camera
> and see it on a dashboard. No other sensors involved.

Camera only, with no second modality to fuse, so this routes to
**`metro-ai-app-recipe`** (a general-purpose vision stack) rather than
`manufacturing-app-recipe`'s multimodal modes. The orchestrator confirms the
video input source and deployment target, then builds.

Output:
- `./pcb-defect-stack/` Docker Compose solution with a solder-defect
  classifier/detector
- An MQTT alert on `alerts/pcb_defect` when the defect count exceeds 0 in a
  10 s window
- A Grafana dashboard at `https://localhost/grafana` with a live annotated
  video panel
