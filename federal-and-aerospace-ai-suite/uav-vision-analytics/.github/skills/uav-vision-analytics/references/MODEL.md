<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Model Reference — UAV Vision Analytics

## Default Model: YOLOv8n-VisDrone

| Property | Value |
|----------|-------|
| Model | YOLOv8n-VisDrone |
| Source | [mshamrai/yolov8n-visdrone](https://huggingface.co/mshamrai/yolov8n-visdrone) |
| Format | OpenVINO IR (FP16 or INT8) |
| Input size | 640×640 |
| Classes | 10 aerial object classes |
| Ultralytics pin | `8.4.67` (newer versions use CumSum detection head — fails on GPU/NPU) |

### VisDrone Classes

| ID | Class |
|----|-------|
| 0 | pedestrian |
| 1 | people |
| 2 | bicycle |
| 3 | car |
| 4 | van |
| 5 | truck |
| 6 | tricycle |
| 7 | awning-tricycle |
| 8 | bus |
| 9 | motor |

---

## Model Download and Export (`make model`)

```bash
cd resources
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt      # includes ultralytics==8.4.67, huggingface-hub

# Download checkpoint from HuggingFace
hf download mshamrai/yolov8n-visdrone best.pt --local-dir ./models/yolov8n-visdrone

# Export to OpenVINO FP16 (recommended — works on CPU, GPU, NPU)
yolo export model=./models/yolov8n-visdrone/best.pt \
     format=openvino dynamic=True opset=18 imgsz=640 half=True

# Output: ./models/yolov8n-visdrone/best_openvino_model/best.xml
```

### INT8 Export (optional, higher accuracy)

```bash
# Fast INT8 (no calibration — seconds)
yolo export model=./models/yolov8n-visdrone/best.pt \
     format=openvino dynamic=True opset=18 imgsz=640

# INT8 with VisDrone calibration (downloads ~1.7 GB dataset)
yolo export model=./models/yolov8n-visdrone/best.pt \
     format=openvino dynamic=True opset=18 imgsz=640 int8=True data=VisDrone.yaml
```

---

## Model Path Inside Container

After export the model must be at:
```
resources/models/yolov8n-visdrone/best_openvino_model/best.xml
resources/models/yolov8n-visdrone/best_openvino_model/best.bin
```

The `resources/` directory is bind-mounted:
```yaml
volumes:
  - "./resources:/home/pipeline-server/resources"
```

Container path referenced in pipelines:
```
/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml
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
model = core.read_model('./resources/models/yolov8n-visdrone/best_openvino_model/best.xml')
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
