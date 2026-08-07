# Export YOLOv8n-VisDrone to OpenVINO — CLI-only (no script needed)

`export_models.py` just glues together two off-the-shelf CLI tools that ship
with `huggingface_hub` and `ultralytics`. You can run the same steps directly
from the command line and skip distributing the `.py` file entirely.

## 1. Create and activate a virtual environment, then install dependencies

```bash
cd federal-aerospace/apps/uav-vision-analytics/resources
python3 -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate

pip install -r requirements.txt
```

(`nncf` is only needed if you plan to use `quantize=8` INT8 export.)

## 2. Download the checkpoint from Hugging Face

```bash
hf download mshamrai/yolov8n-visdrone best.pt --local-dir ./models/yolov8n-visdrone
```

## 3. Export to OpenVINO IR

Run from inside the folder containing `best.pt` (or pass the full path as `model=`).

> Note: newer `ultralytics` releases (8.4.x+) replaced the `half=True` /
> `int8=True` / `opset=` export flags with a single `quantize=` argument
> (`quantize=16` for FP16, `quantize=8` for INT8), and `opset` is not a valid
> argument for `format=openvino`. The commands below are verified against
> `ultralytics==8.4.115`.

**FP16 (default, recommended):**
```bash
yolo export model=./models/yolov8n-visdrone/best.pt format=openvino dynamic=True imgsz=640 quantize=16
```

**FP32:**
```bash
yolo export model=./models/yolov8n-visdrone/best.pt format=openvino dynamic=True imgsz=640
```

**INT8 (requires `nncf`, calibrated quantization):**
```bash
yolo export model=./models/yolov8n-visdrone/best.pt format=openvino dynamic=True imgsz=640 quantize=8
```
By default this calibrates using the small built-in `coco8.yaml` sample set
(fast, a few seconds). For better accuracy on drone imagery, calibrate on
VisDrone instead — note this downloads the full VisDrone dataset (~1.7 GB) on
first run:
```bash
yolo export model=./models/yolov8n-visdrone/best.pt format=openvino dynamic=True imgsz=640 quantize=8 data=VisDrone.yaml
```

Each command creates a `best_openvino_model/` (or `best_int8_openvino_model/`
for INT8) folder next to `best.pt` containing `best.xml` and `best.bin` — the
same output produced by `export_models.py`.

## 4. (Optional) Verify the exported model

```bash
python3 -c "
import openvino as ov
core = ov.Core()
m = core.read_model('./models/yolov8n-visdrone/best_openvino_model/best.xml')
print('OK, inputs:', [i.any_name for i in m.inputs])
"
```
(use `best_int8_openvino_model` in the path if you exported with `quantize=8`.)

## 5. Run inference

```bash
yolo predict model=./models/yolov8n-visdrone/best_openvino_model imgsz=640 source=<image_or_video>
```

or with your own `inference.py` script pointed at the exported `.xml` file.

---

### VisDrone classes
`pedestrian, people, bicycle, car, van, truck, tricycle, awning-tricycle, bus, motor`
