# Dependencies

Install OpenVINO™ and GPU NPU driver
```bash
bash ./install_dependencies.sh
```

## Models

Download and convert YOLO and ResNet models from
https://github.com/openvinotoolkit/openvino_notebooks/blob/2026.0/notebooks/yolov8-optimization/yolov8-object-detection.ipynb
https://github.com/openvinotoolkit/open_model_zoo/blob/master/models/public/resnet-50-tf/README.md

## Build

```bash
bash ./build.sh
```

## Run

Set up the environment variables

```bash
source /opt/intel/vppsdk/env.sh
source /opt/intel/openvino_2025/setupvars.sh
export VPPLOG_LEVEL=error
export FPS_COUNT=1
```

Run the application:

```bash
<app> <model path.xml>
```
