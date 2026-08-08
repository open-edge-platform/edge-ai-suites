# Export YOLOv8n-VisDrone to OpenVINO — CLI-only (no script needed)

`export_models.py` just glues together two off-the-shelf CLI tools that ship
with `huggingface_hub` and `ultralytics`. You can run the same steps directly
from the command line and skip distributing the `.py` file entirely.

## 1. Create and activate a virtual environment, then install dependencies

```bash
cd edge-ai-suites/federal-aerospace/apps/uav-vision-analytics/resources
python3 -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

(`nncf` is only needed if you plan to use `int8=True` INT8 export.)

> ⚠️ **Pin `ultralytics==8.4.67`.** Newer releases (8.4.115+ tested) changed
> the detection head's box-decoding math to use a `CumSum` op instead of
> `Range`. The resulting OpenVINO IR still runs fine on **CPU**, but fails to
> compile/run on **GPU** and **NPU** plugins. `8.4.67` produces a `Range`-based
> graph verified to work on CPU, GPU, and NPU (identical op set to the model
> produced by `export_models.py`). `requirements.txt` already pins this
> version — do not upgrade `ultralytics` without re-verifying GPU/NPU
> compatibility of the exported IR.

## 2. Download the checkpoint from Hugging Face

```bash
hf download mshamrai/yolov8n-visdrone best.pt --local-dir ./models/yolov8n-visdrone
```

## 3. Export to OpenVINO IR

Run from inside the folder containing `best.pt` (or pass the full path as `model=`).

**FP16 (default, recommended — required for GPU/NPU-friendly graph):**
```bash
yolo export model=./models/yolov8n-visdrone/best.pt format=openvino dynamic=True opset=18 imgsz=640 half=True
```

**FP32:**
```bash
yolo export model=./models/yolov8n-visdrone/best.pt format=openvino dynamic=True opset=18 imgsz=640
```

**INT8 (requires `nncf`, calibrated quantization):**
```bash
yolo export model=./models/yolov8n-visdrone/best.pt format=openvino dynamic=True opset=18 imgsz=640 int8=True
```
This calibrates using the small built-in `coco8.yaml` sample set by default
(fast, a few seconds). For better accuracy on drone imagery, calibrate on
VisDrone instead — note this downloads the full VisDrone dataset (~1.7 GB) on
first run:
```bash
yolo export model=./models/yolov8n-visdrone/best.pt format=openvino dynamic=True opset=18 imgsz=640 int8=True data=VisDrone.yaml
```

Each command creates a `best_openvino_model/` (or `best_int8_openvino_model/`
for INT8) folder next to `best.pt` containing `best.xml` and `best.bin` — the
same output produced by `export_models.py`, verified to run on CPU, GPU, and
NPU.

## 4. (Optional) Verify the exported model

```bash
python3 -c "
import openvino as ov
core = ov.Core()
m = core.read_model('./models/yolov8n-visdrone/best_openvino_model/best.xml')
print('OK, inputs:', [i.any_name for i in m.inputs])
"
```
(use `best_int8_openvino_model` in the path if you exported with `int8=True`.)

## 5. Run inference

```bash
yolo predict model=./models/yolov8n-visdrone/best_openvino_model imgsz=640 source=<image_or_video>
```

or with your own `inference.py` script pointed at the exported `.xml` file.

---

### VisDrone classes
`pedestrian, people, bicycle, car, van, truck, tricycle, awning-tricycle, bus, motor`
