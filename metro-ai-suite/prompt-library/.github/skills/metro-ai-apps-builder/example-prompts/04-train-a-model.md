# Train a model — custom detector → getitune pipeline

**User (business objective):**
> I have a labeled dataset of my product on the line and want a model that spots
> defects, ready to run on Intel hardware.

**Orchestrator (Step 1 — business Q&A):**
1. Outcome — a deployable defect-detection model (OpenVINO IR)? [yes]
2. Inputs — where is the dataset and what format (COCO/YOLO/VOC)? [provide path]
3. Task — detection, classification, or segmentation? [detection]
4. Hardware for training — Intel CPU/GPU/XPU? [GPU if available, else CPU]
5. Do you need it quantized (INT8) for speed on the edge? [yes]

**Discovery (Step 2):** verb *train* + object *dataset* → the **`getitune-*`**
training-library skills (sequence). Optionally `geti-using-the-pipeline` if the
user prefers the Geti app REST workflow instead of the library.

**Plan (Step 4 — awaits confirmation):**
- Deliverable: a trained, exported, INT8-quantized OpenVINO IR defect detector +
  validation metrics — ready to feed a deployment skill later.
- Skills (sequence): `getitune-discovering-models` →
  `getitune-preparing-datasets` → `getitune-training-a-model` →
  `getitune-exporting-a-model` → `getitune-optimizing-a-model` →
  `getitune-running-inference`.
- Inferred technology: a detection recipe baseline, device per availability,
  FP32→INT8 via NNCF PTQ.
- Install (after approval): `npx skills@1.5.23 add open-edge-platform/skills --skill getitune-training-a-model` (and the other getitune skills as needed).
- Requirements: Python env for getitune; dataset accessible locally.

**Follow-on:** the resulting IR can be deployed via `model-download-user` →
`metro-ai-apps-recipe` (offer this as the natural next step).
