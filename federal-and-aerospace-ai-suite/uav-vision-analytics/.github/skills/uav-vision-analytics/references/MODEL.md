<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Model Reference — UAV Vision Analytics

## Default Model: YOLO11s

| Property | Value |
|----------|-------|
| Model | YOLO11s |
| Source | Ultralytics (auto-downloaded by the `yolo` CLI from the official release assets — no HuggingFace/API token needed) |
| Format | OpenVINO IR (FP16 or INT8) |
| Input size | 640×640 |
| Classes | 80 classes (person, car, truck, bicycle, motorcycle, ...) |
| Ultralytics pin | `8.4.67` (newer versions use CumSum detection head — fails on GPU/NPU) |

---

## Model Download and Export (`make model`)

```bash
cd resources
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt      # includes ultralytics==8.4.67

mkdir -p models/yolo11s
cd models/yolo11s

# yolo11s.pt is auto-downloaded from Ultralytics' release assets if not
# already present in the current directory — export lands next to it.
yolo export model=yolo11s.pt \
     format=openvino dynamic=True opset=18 imgsz=640 half=True

# Output: ./models/yolo11s/yolo11s_openvino_model/yolo11s.xml
```

### INT8 Export (optional, faster accuracy)

```bash
# Fast INT8 (no calibration — seconds)
yolo export model=yolo11s.pt \
     format=openvino dynamic=True opset=18 imgsz=640

# INT8 with COCO calibration (downloads the small coco8 calibration set)
yolo export model=yolo11s.pt \
     format=openvino dynamic=True opset=18 imgsz=640 int8=True data=coco8.yaml
```

---

## Model Path Inside Container

After export the model must be at:
```
resources/models/yolo11s/yolo11s_openvino_model/yolo11s.xml
resources/models/yolo11s/yolo11s_openvino_model/yolo11s.bin
```

The `resources/` directory is bind-mounted:
```yaml
volumes:
  - "./resources:/home/pipeline-server/resources"
```

Container path referenced in pipelines:
```
/home/pipeline-server/resources/models/yolo11s/yolo11s_openvino_model/yolo11s.xml
```

---

## requirements.txt (for model export)

```
huggingface-hub
ultralytics==8.4.67
```

---

## Verifying the Model

```python
from openvino.runtime import Core
core = Core()
model = core.read_model('./resources/models/yolo11s/yolo11s_openvino_model/yolo11s.xml')
print(f"Inputs:  {[i.shape for i in model.inputs]}")
print(f"Outputs: {[o.shape for o in model.outputs]}")
```

---

## Using a Custom Model

To substitute a custom OpenVINO IR model:

1. Place `model.xml` + `model.bin` under `resources/models/{{MODEL_NAME}}/`
2. Update the `model` property in `config-pymavlink.json` pipeline strings:
   ```
   gvadetect ... model=/home/pipeline-server/resources/models/{{MODEL_NAME}}/model.xml
   ```
3. Update the `MODEL_PATH` constant in `scripts/mavlink_pipeline_manager.py`
4. Verify `threshold` is appropriate for your model (default `0.4`)

**Note:** Only OpenVINO IR format (`.xml` + `.bin`) is supported by `gvadetect`.
ONNX models must be converted first with `mo` (OpenVINO Model Optimizer) or
`openvino.convert_model()`.
