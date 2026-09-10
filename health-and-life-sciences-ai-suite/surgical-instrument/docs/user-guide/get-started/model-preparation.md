# Model Preparation

> Skip this page if you already have a compatible pre-trained model exported to OpenVINO IR.
> This page covers the **local training + export** flow that
> produces the model artifact under `models/yolo11n_polyp/best_openvino_model/`.

The Docker Compose runtime described in [Get Started](../get-started.md) expects
a trained OpenVINO IR to already exist on the host. If you don't have one, this
page walks through building it end-to-end from source dataset to FP16 IR on an
Intel iGPU / Arc GPU.

The bootstrap flow is **cache-first**: it checks for
`models/yolo11n_polyp/best_openvino_model/best.xml` + a `.trained_ok` marker
before doing any work, so re-running `make backend-bootstrap` after a successful
run is effectively a no-op.

---

## 0. Install host prerequisites

`make setup-prerequisites` installs everything the training venv and the Docker Compose runtime
need: base tools, Docker Engine + Compose v2, and the Intel client GPU stack
(Level Zero + OpenCL + iHD VA-API) from the official `intel-graphics` apt repo.

```bash
make setup-prerequisites          # interactive; apt may prompt for confirmation
make setup-prerequisites SETUP_ARGS=-y       # assume-yes to apt
make setup-prerequisites SETUP_ARGS=--dry-run
```

Then verify:

```bash
make check-l0       # dpkg check for libze1, libze-intel-gpu1, libigc2,
                    # libigdgmm12, intel-opencl-icd, intel-media-va-driver-non-free
                    # and /dev/dri device node
```

Log out and back in (or reboot) if `make setup-prerequisites` newly added your user to the
`render`, `video`, or `docker` groups.

---

## 1. Fetch the dataset

The application is validated on **REAL-Colon** (Cosmo Intelligent Medical
Devices, figshare article `22202866`). The full corpus is 60 studies (~880 GB).
The training subset we use is 4 studies (~67 GB).

```bash
make download-dataset    # 4 studies, ~67 GB, to datasets/REAL-Colon/raw/

make prepare-dataset MAX_POS_PER_VIDEO=800 # take maximum 800 positive frames per video

```

---

## 2. Create the training virtualenv

```bash
make backend-venv
```

Creates `.venv-backend/` with:

- `torch==2.7.1` + `torchvision==0.22.1` (both `+xpu` builds from the
  `pytorch/whl/xpu` index) — the Intel iGPU device backend.
- `ultralytics==8.4.75` (YOLO11 training).
- `openvino==2026.2.0` (FP16 IR export).

The venv is host-side (not in a container) so training uses the host's Level
Zero driver and Intel iGPU directly. Requires the L0 stack installed by
`make setup-prerequisites` / verified by `make check-l0`.

---

## 3. Train + export

```bash
make backend-bootstrap
```

Under the hood this runs `python -m backend.main_bootstrap`, which:

1. Auto-extracts dataset archives if needed.
2. Detects the REAL-Colon `*_frames/` + `*_annotations/` layout, converts
   Pascal VOC XML bounding boxes to YOLO labels, and writes a Linux-clean
   `data.yaml` under `datasets/REAL-Colon/` (70/15/15 train/val/test split,
   deterministic seed).
3. Trains YOLO11n on the Intel iGPU (`device: xpu`) for 50 epochs with the
   hyperparameters in `backend/config/model.yaml`. Typical wall time on Arc
   iGPU (Meteor Lake / Lunar Lake / Arrow Lake) is ~20 minutes.
4. Exports the best checkpoint to a FP16 OpenVINO IR at
   `models/yolo11n_polyp/best_openvino_model/best.xml` + `best.bin`.
5. Writes a `.trained_ok` marker so subsequent runs cache-hit.

All defaults are in `backend/config/model.yaml`; override any of them via
environment variables:

```bash
DATASETS_DIR=/data/rc MODELS_DIR=/opt/models make backend-bootstrap
```

Or edit `backend/config/model.yaml` directly (e.g. change `train.epochs`,
`train.batch`, `train.device`, or add extra Ultralytics args).

---

## 4. Generate the demo video (required)

Fresh clones do not include `videos/polyp_test.mp4`. Generate it from the
`surgical-instrument/` workdir before running `make doctor` / `make up`. The
generator stitches frames from the REAL-Colon subset into an H.264 demo clip:

```bash
.venv-backend/bin/python scripts/create_endoscopy_video.py \
  --images-dir datasets/REAL-Colon/raw/001-001_frames \
  --output videos/polyp_test.mp4 \
  --seconds 60 --fps 60 --width 1920 --height 1080
```

---

## 5. Verify and continue

```bash
make doctor           # confirms docker, /dev/dri, cached IR, demo video, L0 stack
make up ...           # continue with the runtime flow in Get Started
```

`make doctor` prints an `[OK] / [MISSING]` line for every prerequisite and
exits non-zero if any hard requirement is missing.

---

## Reset the cache

To rebuild the model from scratch (e.g. after a dataset change):

```bash
rm -rf models/yolo11n_polyp/best_openvino_model \
       models/yolo11n_polyp/.trained_ok \
       datasets/REAL-Colon/data.yaml
make backend-bootstrap
```

The raw dataset archives under `datasets/REAL-Colon/raw/` are left untouched —
only the derived labels, splits, and trained artifacts are regenerated.

See [Troubleshooting](../troubleshooting.md) for the common training-side
failure modes (`torch.xpu unavailable`, `zeInit` errors, dataset auto-detect
failures, etc.).
