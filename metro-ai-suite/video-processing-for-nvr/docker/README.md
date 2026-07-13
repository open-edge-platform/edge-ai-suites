# Build And Run Docker Image

## System requirements

**Operating System:**
* Ubuntu 24.04

**Software:**
* Video Processing Platform SDK

## Build Docker image

1. Build Docker image for reference application `bash build_sample.sh`
Make sure Docker is correctly installed and configured.

## Download the yolov8n_with_preprocess.xml model

1. Download and convert yolo model with [openvino notebook](https://github.com/openvinotoolkit/openvino_notebooks/blob/2026.0/notebooks/yolov8-optimization/yolov8-object-detection.ipynb)

## Run Docker container

1. Run `sudo init 3` switch to non-GUI mode
2. Run a sample test in docker container : `bash run.sh yolov8n_with_preprocess.xml`
To exit the program, you need to open another terminal window and stop the container using docker stop.

## Run Docker Compose

If you want to build the image.Using the provided script to build the image is highly recommended.

```
#Set up environment variables for the model

export MODEL_DIR=your_model_dir

eg:/home/vpp/yolov8n_int8

export MODEL_FILE=your_model_file

eg:yolov8n_with_preprocess.xml

docker compose build
```

1. Run `sudo init 3` switch to non-GUI mode
2. Run `bash ./startup.sh yolov8n_with_preprocess.xml`

If you want to stop the program, press Ctrl+C

Upon successful execution, the following logs will be displayed:
```
vppsample-1  | [2026-06-01 21:25:14.085] [thread 327] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.085] [thread 337] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.085] [thread 329] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.085] [thread 335] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.085] [thread 339] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.087] [thread 325] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.087] [thread 327] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.087] [thread 337] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.087] [thread 340] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.087] [thread 329] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.087] [thread 338] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.087] [thread 327] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.087] [thread 332] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.088] [thread 339] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.088] [thread 336] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | Detected box: index=1, left=1489, top=0, width=342, height=90
vppsample-1  | [2026-06-01 21:25:14.089] [thread 325] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.089] [thread 338] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.089] [thread 329] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.089] [thread 340] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.089] [thread 337] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.089] [thread 327] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.089] [thread 339] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.089] [thread 336] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.089] [thread 332] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.090] [thread 334] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.091] [thread 332] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.091] [thread 337] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.091] [thread 337] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | [2026-06-01 21:25:14.091] [thread 332] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | Detected box: index=6, left=492, top=0, width=658, height=239
vppsample-1  | Detected box: index=13, left=636, top=813, width=990, height=260
vppsample-1  | Detected box: index=0, left=1485, top=0, width=344, height=90
vppsample-1  | [2026-06-01 21:25:14.091] [thread 340] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | Detected box: index=1, left=1489, top=0, width=342, height=90
vppsample-1  | [2026-06-01 21:25:14.093] [thread 335] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.093] [thread 334] [info]: [decode.cpp:getFrame@Line1434] decode get frame
vppsample-1  | Detected box: index=1, left=723, top=229, width=834, height=697
vppsample-1  | Detected box: index=0, left=1458, top=0, width=370, height=92
vppsample-1  | [2026-06-01 21:25:14.094] [thread 326] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
vppsample-1  | [2026-06-01 21:25:14.094] [thread 330] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame


vppsample-1 exited with code 0
vppsample-1  | [2026-06-01 21:25:14.097] [thread 328] [info]: [decode.cpp:releaseFrame@Line1492] decode release frame
```

## Uninstall Docker image

1. Run `docker rmi -f $(docker images --format "{{.Repository}}:{{.Tag}}" | grep 'vppsample')` to remove all vppsample Docker images.

## Caution

This container image is intended for demo purposes only and not intended for production use. To receive expanded security maintenance from Canonical on the Ubuntu base layer, you may follow the [how-to guide to enable Ubuntu Pro in a Dockerfile](https://documentation.ubuntu.com/pro-client/en/docs/howtoguides/enable_in_dockerfile) which will require the image to be rebuilt.
