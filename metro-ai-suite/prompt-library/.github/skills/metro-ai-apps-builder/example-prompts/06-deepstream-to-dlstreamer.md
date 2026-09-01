# DeepStream → DL Streamer migration — custom pipeline code → `dlstreamer-coding-agent`

**User (business objective):**
> I already have an NVIDIA DeepStream app that detects vehicles from my camera
> and draws boxes on the stream. I want the same thing running on my Intel box.

**Orchestrator (Step 1 — business Q&A, batched):**
1. Outcome — reproduce your DeepStream detection + on-frame overlay as an
   equivalent Intel pipeline? [yes]
2. Inputs — an ONVIF camera [default], live RTSP/USB, or a sample video? [ONVIF]
3. Deliverable — a runnable DL Streamer app/pipeline you can edit, or a fully
   deployed stack? [runnable pipeline/app]
4. Hardware — Intel GPU (default), or Intel CPU/NPU? [Intel GPU]
5. Model — reuse your existing detector, or an equivalent OpenVINO model? [equivalent OpenVINO IR]

**Discovery (Step 2):** verb *migrate/convert* + object *DeepStream pipeline* →
**`dlstreamer-coding-agent`** (authors equivalent Intel DL Streamer code:
GStreamer/`gvadetect`/`gvawatermark`). Not in this repo — install from
`open-edge-platform/dlstreamer`. Supporting **`model-download-user`** when the
NVIDIA model needs an OpenVINO IR equivalent.

**Plan (Step 4 — presented, awaits confirmation):**
- Deliverable: a DL Streamer pipeline/app mirroring the DeepStream graph
  (source → detect → overlay → sink), runnable on the user's Intel host.
- Skills (sequence): `model-download-user` (equivalent detector IR) →
  `dlstreamer-coding-agent` (author the pipeline).
- Inferred technology (decisions, not questions): DeepStream `nvinfer` →
  `gvadetect`, `nvdsosd` → `gvawatermark`, `nvstreammux`/`nvvideoconvert` →
  standard GStreamer `videoconvert`; YOLO-family vehicle detector as OpenVINO
  INT8 IR; Intel GPU inference; ONVIF camera source.
- Requirements: Node 20+ / `npx skills@1.5.23` to install the delegate; Intel GPU
  drivers for GPU inference; OpenVINO runtime.
- Install command (run only after approval):
  `npx skills@1.5.23 add open-edge-platform/dlstreamer --skill dlstreamer-coding-agent`

**Build (Step 5, after "go"):** delegate to `dlstreamer-coding-agent`, passing the
inferred element mapping, model IR, `DEVICE=GPU`, and the ONVIF source. Verify
against that skill's completion criteria (the pipeline runs and emits detections
with overlay), then show the user the command to run it.
