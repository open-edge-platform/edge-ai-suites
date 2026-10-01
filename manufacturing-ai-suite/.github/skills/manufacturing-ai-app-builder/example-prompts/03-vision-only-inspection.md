# Vision only — camera-based PCB defect detection

**User (business objective):**
> I want to spot defective solder joints on PCBs from my inspection camera
> and see it on a dashboard. No other sensors involved.

**Orchestrator (Step 1 — business Q&A, batched):**
1. Outcome — flag a defective solder joint per board? [yes]
2. What feeds this — a camera, a sensor, or both together? [camera only]
3. Inputs — camera: sample PCB inspection video, or a real RTSP/USB feed?
   [sample video]
4. Deployment — quick local demo, single-host Docker solution, or
   Kubernetes? [single-host Docker]
5. Do you need a live annotated video wall + alert dashboard? [yes]

**Discovery (Step 2):** "what feeds this" = camera only, no sensor to
correlate against → **`metro-ai-app-recipe`** (vision-only end-to-end stack;
already covers the "Industrial / logistics" vertical, including
surface-defect detection). Not routed to `manufacturing-multimodal-app-recipe`
— there is no second modality to fuse.

**Plan (Step 4 — presented, awaits confirmation):**
- Deliverable: `./pcb-defect-stack/` Docker Compose solution; Grafana-based
  dashboard at `https://localhost/grafana` with live annotated WebRTC panels
  + defect-count alerts.
- Skill: `metro-ai-app-recipe` (already available in this workspace).
- Supporting: `model-download-user` if a custom solder-defect IR is needed;
  `dlstreamer-coding-agent` only if a from-scratch pipeline is requested
  instead of the standard classify/detect shape.
- Inferred technology (decisions, not questions): a defect classifier/detector
  on CPU (or GPU if available), Node-RED rule `count>0 in 10s`, MQTT alert
  topic `alerts/pcb_defect`.
- Requirements: Docker + Compose v2; ports 80/443 and 3478/udp free.

**Build (Step 5, after "go"):** delegate to `metro-ai-app-recipe`, passing the
inferred `{{OBJECT}}=pcb_defect`, `{{STACK_DIR}}=pcb-defect-stack`, rule, and
topics. Verify against that skill's completion criteria, then tell the user
how to open the dashboard.

**Key behavior:** even though the objective is manufacturing-domain, a
single-modality (camera-only) request routes to the general-purpose vision
recipe, not one of the two manufacturing-specific fusion/sensor skills —
`manufacturing-ai-app-builder` only special-cases routing when a sensor
signal is genuinely part of the decision.
