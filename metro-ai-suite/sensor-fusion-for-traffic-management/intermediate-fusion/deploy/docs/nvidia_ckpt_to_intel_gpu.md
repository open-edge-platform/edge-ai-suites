# Running NVIDIA's V2X-I PointPillars Dense FP16 Model on Intel GPU

**Purpose.** This guide describes how to take a model trained with NVIDIA's [CUDA-V2XFusion](https://github.com/NVIDIA-AI-IOT/Lidar_AI_Solution/tree/master/CUDA-V2XFusion) reference design and deploy it on Intel GPU via the [applications.iot.video-edge-cloud.gpu-bev-fusion](https://github.com/intel-innersource/applications.iot.video-edge-cloud.gpu-bev-fusion) deploy binary.

**Audience.** Customers who already hold a CUDA-V2XFusion-trained checkpoint — either NVIDIA's provided reference model `dense_epoch_100_.pth`, or a checkpoint you produced yourself by following NVIDIA's reference training flow — and want to run inference on Intel platform without any retraining or C++ changes on the deploy side.

**Scope.** Weight conversion only: take a CUDA-V2XFusion `.pth`, produce the 4-ONNX + INT8 OpenVINO IR artifacts the Intel deploy binary expects, install them, and run the binary end-to-end. No retraining, no mmdet3d edits, no config edits. Pipeline A (split 4-ONNX) only.

---

## 1. Overview

```
 dense_epoch_100_.pth  (NVIDIA reference model)
          │
          ▼
 [FP32 export]           ─> export/V2X-I/pp/
   export_all.py              camera.backbone.onnx   (~85 MB)
                              lidar_pfe.onnx         (~18 KB, dynamic V)
                              fuser.onnx             (~48 MB)
                              head.onnx              (~2.4 MB)
          │
          ▼
 [Static V=6000 PFE]     ─> export/V2X-I/pp/
   export-lidar.py            lidar_pfe_v6000.onnx   (~4.8 MB)
          │
          ▼
 [INT8 PTQ (NNCF)]       ─> export/V2X-I/pp/
   quantize_all.py            quantized_camera.{xml,bin}
                              quantized_lidar_pfe.{xml,bin}
                              quantized_fuser.{xml,bin}
                              quantized_head.{xml,bin}
          │
          ▼
 [Copy to deploy tree]   ─> applications.iot.video-edge-cloud.gpu-bev-fusion/
                              deploy/data/v2xfusion/pointpillars/
          │
          ▼
 [Run on Intel GPU]      cd deploy/build && ./bevfusion <dataset> --preset v2x --int8
```

The entire left column (export + quantize) happens inside NVIDIA's bevfusion training repo after you apply the patch bundle this guide ships. The deploy binary already knows how to consume the files produced.

---

## 2. Prerequisites

### 2.1 Set up NVIDIA's bevfusion training repo

Follow NVIDIA's own instructions at [Lidar_AI_Solution/CUDA-V2XFusion/README.md](https://github.com/NVIDIA-AI-IOT/Lidar_AI_Solution/tree/master/CUDA-V2XFusion) to:

1. Clone MIT BEVFusion at the commit NVIDIA pins.
2. Layer the BEVHeight and CUDA-V2XFusion patches on top as described in NVIDIA's README.
3. Install the Python environment: Python 3.8, `torch==1.11`, `mmcv`, `mmdet3d`, `torchpack`, and the usual MIT BEVFusion dependencies.

Do not attempt to run training — you only need the Python environment and the configs.

### 2.2 Download NVIDIA's reference checkpoint

Grab `dense_epoch_100_.pth` per NVIDIA's CUDA-V2XFusion README. Note its absolute path — you will pass it to the export and quantize commands.

### 2.3 Add ONNX export + INT8 PTQ dependencies

In the same Python environment you set up in §2.1, install the extras used by the scripts shipped with this guide:

```bash
pip install "nncf>=2.13" "openvino>=2024.4" "onnx" "onnxsim"
```

That is everything. The export and quantize scripts reuse `mmdet3d`, `mmcv`, and `torchpack` that are already present from §2.1.

### 2.4 Clone the deploy repo and build it

Clone [applications.iot.video-edge-cloud.gpu-bev-fusion](https://github.com/intel-innersource/applications.iot.video-edge-cloud.gpu-bev-fusion) and follow its own documentation for the build:

- `deploy/README.md` — top-level build instructions.
- `deploy/docs/Prerequisites.md` — oneAPI + custom OpenVINO installation.
- `deploy/docs/GSG.md` — full getting-started guide with build and run commands.

**We deliberately do not duplicate those instructions here.** Once you have a working `deploy/build/bevfusion` binary and its default dataset directory, come back to this guide.

---

## 3. Step 1 — Apply the patch bundle

From the root of your NVIDIA bevfusion clone (the directory that contains `tools/`, `mmdet3d/`, `configs/`), run:

```bash
cp -r /path/to/this/Guide/nvidia_ckpt_to_intel_gpu_patches/* .
```

That drops 12 files under `export/pointpillars/` (see [Appendix A](#appendix-a--what-the-patch-bundle-adds) for the exact list). No existing file is touched — this is a pure addition.

Sanity check:

```bash
ls export/pointpillars/
# expected:
#   __init__.py  _calib_data.py
#   export_all.py  export-camera.py  export-lidar.py  export-fuser.py  export-head.py
#   quantize_all.py  quantize_camera_backbone.py  quantize_lidar_pfe.py  quantize_fuser.py  quantize_head.py
```

---

## 4. Step 2 — FP32 ONNX export (4 sub-graphs)

The deploy binary splits the BEVFusion graph into four independently-loaded ONNX sub-graphs. Export all of them at once:

```bash
python export/pointpillars/export_all.py \
  --config configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml \
  --ckpt /path/to/dense_epoch_100_.pth \
  --out-dir export/V2X-I/pp/
```

Expected tail output:

```
[cam-export]   reference shapes: feat=(1, 80, 54, 96) depth=(1, 90, 54, 96)
[cam-export]   saved to export/V2X-I/pp/camera.backbone.onnx
[lidar-export] saved to export/V2X-I/pp/lidar_pfe.onnx
[fuser-export] saved to export/V2X-I/pp/fuser.onnx
[head-export]  saved to export/V2X-I/pp/head.onnx

SUMMARY
  [OK] camera   export/V2X-I/pp/camera.backbone.onnx  (~88 MB)
  [OK] lidar    export/V2X-I/pp/lidar_pfe.onnx       (~18 KB)
  [OK] fuser    export/V2X-I/pp/fuser.onnx           (~50 MB)
  [OK] head     export/V2X-I/pp/head.onnx            (~2.4 MB)
```

### Benign warnings you will see and can ignore

- **`missing keys in source state_dict: encoders.camera.vtransform.cx`** — `cx` is a non-learnable buffer used only for BEV coordinate offset; model `__init__` fills the default value. Not present in NVIDIA's ckpt, harmless for inference.
- **`unexpected key in source state_dict: fc.weight, fc.bias`** — these come from the ResNet34 ImageNet-pretrained fc layer that BEVFusion never uses.

---

## 5. Step 3 — Export the static V=6000 PFE

The Intel deploy binary's split pipeline hard-codes a maximum of 6000 voxels per frame (see `deploy/src/pipeline/split_pipeline_config.cpp` around lines 110–127). You therefore need a second PFE ONNX with a fixed batch-voxel dimension of 6000 in addition to the dynamic-V version from Step 2:

```bash
python export/pointpillars/export-lidar.py \
  --config configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml \
  --ckpt /path/to/dense_epoch_100_.pth \
  -o export/V2X-I/pp/lidar_pfe_v6000.onnx \
  --fixed-v 6000 \
  --split val
```

Expected tail output:

```
[lidar-export] tracing from cfg.data.val
[lidar-export] traced shapes: features=(5137, 100, 4) num_voxels=(5137,) coors=(5137, 4)
[lidar-export] wrapper vs pfe max-abs-diff = 0.000004
[lidar-export] exporting with FIXED V=6000 (measured dataset max V=6295, using safety margin)
[lidar-export] fixed-V sanity OK (no NaN), output (6000, 64)
[lidar-export] saved to export/V2X-I/pp/lidar_pfe_v6000.onnx
```

**Important — do not drop `--split val`.** The `--split` argument tells the tracer to pull a real frame from `cfg.data.val`, which determines the activation distribution the INT8 calibrator will see later. Using a trace frame from a mismatched dataset layout is a silent correctness bug.

---

## 6. Step 4 — INT8 PTQ quantization

Calibrate and quantize the four ONNX models to INT8 OpenVINO IR:

```bash
python export/pointpillars/quantize_all.py \
  --config configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml \
  --ckpt /path/to/dense_epoch_100_.pth \
  --onnx-dir export/V2X-I/pp/ \
  --out-dir  export/V2X-I/pp/ \
  --num-samples 300
```

**Run this with the same Python interpreter you used in Steps 2 and 3.** The quantize scripts call into `mmdet3d` and `torchpack` to build real calibration samples, so they need the same mmdet3d-capable environment, not a separate NNCF-dedicated env.

Expected tail output:

```
SUMMARY
  [OK] camera     export/V2X-I/pp/quantized_camera.xml      (~420 KB) + .bin (~22 MB)
  [OK] lidar_pfe  export/V2X-I/pp/quantized_lidar_pfe.xml   (~73 KB)  + .bin (~2.5 MB)
  [OK] fuser      export/V2X-I/pp/quantized_fuser.xml       (~208 KB) + .bin (~12.5 MB)
  [OK] head       export/V2X-I/pp/quantized_head.xml        (~216 KB) + .bin (~614 KB)
```

`quantize_all.py` auto-detects `lidar_pfe_v6000.onnx` in `--onnx-dir` and uses it in preference to the dynamic-V PFE, which is what the deploy binary expects for INT8.

---

## 7. Step 5 — Install artifacts into the deploy tree

The deploy binary looks for its model files under `deploy/data/v2xfusion/pointpillars/` by default for `--preset v2x`. Copy both the FP32 fallback ONNXs and the INT8 IRs into that directory:

```bash
DEPLOY_DIR=/path/to/applications.iot.video-edge-cloud.gpu-bev-fusion/deploy/data/v2xfusion/pointpillars

mkdir -p "$DEPLOY_DIR"

# FP32 fallbacks
cp export/V2X-I/pp/camera.backbone.onnx    "$DEPLOY_DIR/"
cp export/V2X-I/pp/lidar_pfe.onnx          "$DEPLOY_DIR/"
cp export/V2X-I/pp/lidar_pfe_v6000.onnx    "$DEPLOY_DIR/"
cp export/V2X-I/pp/fuser.onnx              "$DEPLOY_DIR/"
cp export/V2X-I/pp/head.onnx               "$DEPLOY_DIR/"

# INT8 IR pairs
cp export/V2X-I/pp/quantized_camera.xml    "$DEPLOY_DIR/"
cp export/V2X-I/pp/quantized_camera.bin    "$DEPLOY_DIR/"
cp export/V2X-I/pp/quantized_lidar_pfe.xml "$DEPLOY_DIR/"
cp export/V2X-I/pp/quantized_lidar_pfe.bin "$DEPLOY_DIR/"
cp export/V2X-I/pp/quantized_fuser.xml     "$DEPLOY_DIR/"
cp export/V2X-I/pp/quantized_fuser.bin     "$DEPLOY_DIR/"
cp export/V2X-I/pp/quantized_head.xml      "$DEPLOY_DIR/"
cp export/V2X-I/pp/quantized_head.bin      "$DEPLOY_DIR/"
```

If you want to keep multiple model variants side by side, you can put them under any directory and point the deploy binary at it explicitly with `--model-dir` (see Step 6).

---

## 8. Step 6 — Run the deploy binary

Source the oneAPI and OpenVINO environments exactly as the deploy repo's own `deploy/README.md` / `deploy/docs/GSG.md` describe, then:

```bash
cd /path/to/applications.iot.video-edge-cloud.gpu-bev-fusion/deploy/build
./bevfusion /path/to/v2x_dataset --preset v2x --int8 --num-samples 30 --vis --save-video --vis-dir ./viz
```

Key flags:

| Flag | Meaning |
|---|---|
| `--preset v2x` | V2X-I geometry, BEV grid 128×128, pc_range Y ∈ [-51.2, 51.2] |
| `--int8` | Use all four `quantized_*.xml` IRs (falls back to FP32 ONNX per stage if a file is missing) |
| `--int8-camera` / `--int8-pfe` / `--int8-fuser` / `--int8-head` | Toggle INT8 stage-by-stage |
| `--model-dir DIR` | Override the default `data/v2xfusion/pointpillars/` location |
| `--num-samples N` | Process the first N frames |
| `--dump-pred --pred-dir DIR` | Write KITTI-format per-frame box `.txt` files |
| `--vis --save-video --vis-dir DIR` | Write `bevfusion.mp4` and optional per-frame PNGs |

Refer to the deploy repo's own `deploy/docs/GSG.md` for the authoritative full flag list and expected performance figures on the target GPU.

---

## 9. Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| Warning `missing keys in source state_dict: encoders.camera.vtransform.cx` | Benign. NVIDIA's ckpt lacks this non-learnable buffer; the model default fills it. No action. |
| Warning `unexpected key in source state_dict: fc.weight, fc.bias` | Benign. ResNet34 ImageNet-pretrained fc layer that BEVFusion doesn't use. No action. |
| `ModuleNotFoundError: No module named 'torchpack'` during Step 4 | You're running the quantize scripts in a different Python env than Step 2/3. Use the same mmdet3d-capable environment for all three steps. |
| `ModuleNotFoundError: No module named 'nncf'` | Step 2.3 was skipped — install `nncf`, `openvino`, `onnx`, `onnxsim` into the env you are using. |
| PFE INT8 numerically collapsed (poor detections with `--int8-pfe`) | Re-run Step 3 **with `--split val`**. Using a mismatched trace source produces wrong activation scales and the calibrator bakes them in. |
| Deploy binary silently runs FP32 even with `--int8` | One of the `quantized_*.xml` / `.bin` files is missing in the deploy model directory. Re-check Step 5. The deploy binary falls back to FP32 per stage when the INT8 IR is absent. |
| FP32 fuser used despite `--int8` on Intel Arc B580 (Battlemage) | Expected behavior. The deploy binary has a known B580-specific INT8 fuser fallback; the other three stages still run INT8. See the deploy repo's own notes. |
| `onnx.checker` failure on `camera.backbone.onnx` | The `onnxsim` simplification step during Step 2 may have failed silently if you're on a very old `onnxsim`. Upgrade: `pip install -U onnxsim onnx`. |

---

## Appendix A — What the patch bundle adds

```
<nv_bevfusion_root>/
└── export/
    └── pointpillars/
        ├── __init__.py                     (empty, makes the folder a package)
        ├── _calib_data.py                  (shared PyTorch-side calibration helper)
        ├── export_all.py                   (FP32 export orchestrator)
        ├── export-camera.py                (ResNet34 backbone + LSS neck + depthnet → camera.backbone.onnx)
        ├── export-lidar.py                 (PillarFeatureNet → lidar_pfe[,_v6000].onnx)
        ├── export-fuser.py                 (ConvFuser + decoder → fuser.onnx)
        ├── export-head.py                  (CenterHead → head.onnx, 12 output tensors)
        ├── quantize_all.py                 (INT8 PTQ orchestrator, auto-picks v6000 PFE)
        ├── quantize_camera_backbone.py     (NNCF PTQ on camera.backbone.onnx)
        ├── quantize_lidar_pfe.py           (NNCF PTQ on lidar_pfe_v6000.onnx)
        ├── quantize_fuser.py               (NNCF PTQ on fuser.onnx)
        └── quantize_head.py                (NNCF PTQ on head.onnx)
```

Nothing under `mmdet3d/`, `configs/`, or `tools/` is touched. The patch is purely additive.

## Appendix B — Why NVIDIA's ckpt works without any code/config changes

- **State dict shape** — the NVIDIA checkpoint and a model built from `configs/V2X-I/det/centerhead/lssfpn/camera+pointpillar/resnet34/default.yaml` agree on every weight tensor's shape. The only difference is the 3-element `encoders.camera.vtransform.cx` buffer, which is a non-learnable constant that the model constructor fills with the default.
- **Pipeline A does not touch LSS's `get_cam_feats()`** — `export-camera.py` exports `backbone → neck → depthnet` directly and does the per-pixel depth softmax inline, so any downstream `use_bevpool` branching in `mmdet3d/models/vtransforms/lss.py` is irrelevant.
- **ResNet34 pretrained URL vs local path** — NVIDIA's config references the remote pretrained URL; the only effect is where the ImageNet init comes from. Those weights are overwritten by the NVIDIA checkpoint anyway, so this mismatch is invisible at inference time.
- **`strict=False`** — every export and quantize script loads the checkpoint with `strict=False`, so the `cx` missing-key and the ResNet34 `fc.*` extra-keys warnings are just logs, not errors.
