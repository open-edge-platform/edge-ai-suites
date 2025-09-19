# Advanced User Guide

## Overview

This document introduces an Intel® software reference implementation (SW RI) for Metro AI Suite Sensor Fusion in Traffic Management. It combines camera and mmWave radar data—referred to as ISF "C+R" or AIO "C+R"—and runs on the NEPRA base platform.

The internal project code name is **Garnet Park**.

As shown in Fig.1, the end-to-end pipeline includes the following major blocks (workloads):

-   Loading datasets and converting formats

-   Processing radar signals

-   Running video analytics

-   Fusing data from radar and camera

-   Visualization

All these tasks run on single Intel SoC processor which provides all the required heterogeneous computing capabilities. To maximize its performance on Intel processors, we optimized this SW RI using Intel SW tool kits in addition to open-source SW libraries.

![Case1-1C1R](./_images/Case1-1C1R.png)
<center>(1) Use case#1: 1C+1R</center>

![Case2-4C4R](./_images/Case2-4C4R.png)
<center>(2) Use case#2: 4C+4R </center>

![Case3-2C1R](./_images/Case3-2C1R.png)
<center>(3) Use case#3: 2C+1R </center>

![Case4-16C4R](./_images/Case4-16C4R.png)
<center>(4) Use case#4: 16C+4R </center>

<center> Figure 1. E2E SW pipelines of 4 use cases of sensor fusion C+R(Camera+Radar).</center>

### Prerequisites

- Operating System: [Ubuntu 22.04.1 Desktop LTS](https://old-releases.ubuntu.com/releases/22.04.1/ubuntu-22.04.1-desktop-amd64.iso) (fresh installation) on target system

- Platform

    - Intel® Celeron® Processor 7305E (1C+1R/2C+1R usecase)
    - Intel® Core™ Ultra 7 Processor 165H (4C+4R usecase)
    - Intel® Core™ i7-13700 and Intel® Arc™ A770 Graphics (16C+4R usecase)

- Intel® OpenVINO™ Toolkit

    - Version Type: 2025.2

- RADDet Dataset

    - https://github.com/ZhangAoCanada/RADDet#Dataset

    - A processed data snippet is provided in [demo](../../ai_inference/test/demo/raddet_bin_files)

    - If you want to generate the data independently, refer to this guide: [how_to_get_RADDet_datasets.md](How-To-Get-RADDET-Dataset.md)

        Upon success, bin files will be extracted, save to $RADDET_DATASET_ROOT/bin_files_{VERSION}:

        > NOTE: latest converted dataset version should be: v1.0

- Ensure that proxy settings are configured if target system is within proxy environment

    ```bash
    export http_proxy=<Your-Proxy>
    export https_proxy=<Your-Proxy>
    ```

    ```bash
    sudo vim /etc/environment
    # set proxy in /etc/environment
    # http_proxy=<Your-Proxy>
    # https_proxy=<Your-Proxy>
    ```



### Modules

-   AI Inference Service:

    -   Media Processing (Camera)

    -   Radar Processing (mmWave Radar)

    -   Sensor Fusion

-   Demo Application

#### AI Inference Service

AI Inference Service is based on the HVA pipeline framework. In this SW RI, it includes the functions of DL inference, radar signal processing, and data fusion.

AI Inference Service exposes both RESTful API and gRPC API to clients, so that a pipeline defined and requested by a client can be run within this service.

-   RESTful API: listens to port 50051

-   gRPC API: listens to port 50052
```bash
vim $PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config
...
[HTTP]
address=0.0.0.0
RESTfulPort=50051
gRPCPort=50052
```


#### Demo Application
![Demo-1C1R](./_images/Demo-1C1R.png)
<center>Figure 2. Visualization of 1C+1R results</center>

Currently we support four display types: media, radar, media_radar, media_fusion. 





##	System Requirements

### Hardware requirements

- Platform

    - Intel® Celeron® Processor 7305E (1C+1R/2C+1R usecase)
    - Intel® Core™ Ultra 7 Processor 165H (4C+4R usecase)

    - Intel® Core™ i7-13700 and Intel® Arc™ A770 Graphics (16C+4R usecase)

- BIOS setting

    - MTL

        | Setting                                          | Step                                                         |
        | ------------------------------------------------ | ------------------------------------------------------------ |
        | Enable the Hidden BIOS Setting in Seavo Platform | "Right Shift+F7" Then Change Enabled Debug Setup Menu from [Enabled] to [Disable] |
        | Disable VT-d in BIOS                             | Intel Advanced Menu → System Agent (SA) Configuration → VT-d setup menu → VT-d<Disabled>    <br>Note: If VT-d can’t be disabled, please disable Intel Advanced Menu → CPU Configuration → X2APIC |
        | Disable SAGV in BIOS                             | Intel Advanced Menu → [System Agent (SA) Configuration]  →  Memory configuration →  SAGV <Disabled> |
        | Enable NPU Device                                | Intel Advanced Menu → CPU Configuration → Active SOC-North Efficient-cores <ALL>   <br>Intel Advanced Menu → System Agent (SA) Configuration → NPU Device <Enabled> |
        | TDP Configuration                                | SOC TDP configuration is very important for performance. Suggestion: TDP = 45W. For extreme heavy workload, TDP = 64W <br>---TDP = 45W settings: Intel Advanced → Power & Performance → CPU - Power Management Control → Config TDP Configurations → Power Limit 1 <45000> <br>---TDP = 64W settings: Intel Advanced → Power & Performance → CPU - Power Management Control → Config TDP Configurations →  Configurable TDP Boot Mode [Level2] |

    - RPL-S+A770

        | Setting                  | Step                                                         |
        | ------------------------ | ------------------------------------------------------------ |
        | Enable ResizeBar in BIOS | Intel Advanced Menu -> System Agent (SA) Configuration -> PCI Express Configuration -> PCIE Resizable BAR Support <Enabled> |



### Software requirements

| Software           | Version                |
| ------------------ | ---------------------- |
| Intel  OpenVINO    | 2025.2.0               |
| Intel  oneMKL      | 2025.1.0               |
| NEO OpenCL         | Release/23.22.26516.25 |
| cmake              | 3.21.2                 |
| boost              | 1.83.0                 |
| spdlog             | 1.8.2                  |
| thrift             | 0.18.1                 |
| gRPC               | 1.58.1                 |
| zlib               | 1.3.1                 |
| oneAPI Level  Zero | 1.17.19                |



## Install Dependencies and Build Project

* install driver related libs

  Update kernel, install GPU and NPU(MTL only) driver.

  ```bash
  bash install_driver_related_libs.sh
  ```

  Note that this step may restart the machine several times. Please rerun this script after each restart until you see the output of `All driver libs installed successfully`.

* install project related libs

  Install Boost, Spdlog, Thrift, MKL, OpenVINO, GRPC, Level Zero, oneVPL etc.

  ```bash
  bash install_project_related_libs.sh
  ```

- set $PROJ_DIR
  ```bash
  cd metro-ai-suite/sensor-fusion-for-traffic-management
  export PROJ_DIR=$PWD
  ```
- prepare global radar configs in folder: /opt/datasets
    ```bash
    sudo ln -s $PROJ_DIR/ai_inference/deployment/datasets /opt/datasets
    ```

- prepare models in folder: /opt/models
    ```bash
    sudo ln -s $PROJ_DIR/ai_inference/deployment/models /opt/models
    ```
- prepare offline radar results for 4C4R/16C4R:
    ```bash
    sudo cp $PROJ_DIR/ai_inference/deployment/datasets/radarResults.csv /opt
    ```
- build project
    ```bash
    bash -x build.sh
    ```

## How it works

In this section, we describe how to run Intel® Metro AI Suite Sensor Fusion for Traffic Management application.

Intel® Metro AI Suite Sensor Fusion for Traffic Management application can support different pipeline using topology JSON files to describe the pipeline topology. The defined pipeline topology can be found at [sec 4.1 Resources Summary](#41-resources-summary)

There are two steps required for running the sensor fusion application:
- Start AI Inference service, more details can be found at [sec 4.2 Start Service](#42-start-service)
- Run the application entry program, more details can be found at [sec 4.3 Run Entry Program](#43-run-entry-program)

Besides, users can test each component (without display) following the guides at [sec 4.3.2 1C1R Unit Tests](#432-1c+1r-unit-tests), [sec 4.3.4 4C4R Unit Tests](#434-4c+4r-unit-tests), [sec 4.3.6 2C1R Unit Tests](#436-2c+1r-unit-tests), [sec 4.3.8 16C4R Unit Tests](#438-16c+4r-unit-tests)


### Resources Summary
- Local File Pipeline for Media pipeline
  - Json File: localMediaPipeline.json
    `File location: ai_inference/test/configs/raddet/1C1R/localMediaPipeline.json`
  - Pipeline Description: 
    ```
    input -> decode -> detection -> tracking -> output
    ```

- Local File Pipeline for mmWave Radar pipeline
  - Json File: localRadarPipeline.json
    `File location: ai_inference/test/configs/raddet/1C1R/localRadarPipeline.json`
  - Pipeline Description: 

    ```
    input -> preprocess -> radar_detection -> clustering -> tracking -> output
    ```

- Local File Pipeline for `Camera + Radar(1C+1R)` Sensor fusion pipeline

  - Json File: localFusionPipeline.json
    `File location: ai_inference/test/configs/raddet/1C1R/localFusionPipeline.json`
  - Pipeline Description: 
    ```
    input  | -> decode     -> detector         -> tracker                  -> |
           | -> preprocess -> radar_detection  -> clustering   -> tracking -> | -> coordinate_transform->fusion -> output
    ```
- Local File Pipeline for `Camera + Radar(4C+4R)` Sensor fusion pipeline

  - Json File: localFusionPipeline.json
    `File location: ai_inference/test/configs/raddet/4C4R/localFusionPipeline.json`
  - Pipeline Description: 
    ```
    input  | -> decode     -> detector         -> tracker                  -> |
           |              -> radarOfflineResults ->                           | -> coordinate_transform->fusion -> |
    input  | -> decode     -> detector         -> tracker                  -> |                                    |
           |              -> radarOfflineResults ->                           | -> coordinate_transform->fusion -> | -> output
    input  | -> decode     -> detector         -> tracker                  -> |                                    |
           |              -> radarOfflineResults ->                           | -> coordinate_transform->fusion -> |
    input  | -> decode     -> detector         -> tracker                  -> |                                    |
           |              -> radarOfflineResults ->                           | -> coordinate_transform->fusion -> |
    ```

- Local File Pipeline for `Camera + Radar(2C+1R)` Sensor fusion pipeline

    - Json File: localFusionPipeline.json
      `File location: ai_inference/test/configs/raddet/2C1R/localFusionPipeline.json`

    - Pipeline Description: 

        ```
               | -> decode     -> detector         -> tracker                  -> |                                    |
        input  | -> decode     -> detector         -> tracker                  -> | ->  Camera2CFusion ->  fusion   -> | -> output
               | -> preprocess -> radar_detection  -> clustering   -> tracking -> |                                    |
        ```

- Local File Pipeline for `Camera + Radar(16C+4R)` Sensor fusion pipeline

    - Json File: localFusionPipeline.json
      `File location: ai_inference/test/configs/raddet/16C4R/localFusionPipeline.json`

    - Pipeline Description: 

        ```
               | -> decode     -> detector         -> tracker                  -> |                                    |
               | -> decode     -> detector         -> tracker                  -> |                                    |
        input  | -> decode     -> detector         -> tracker                  -> |->  Camera4CFusion ->  fusion   ->  |
               | -> decode     -> detector         -> tracker                  -> |                                    |
               |              -> radarOfflineResults ->                           |                                    |
               | -> decode     -> detector         -> tracker                  -> |                                    |
               | -> decode     -> detector         -> tracker                  -> |                                    |
        input  | -> decode     -> detector         -> tracker                  -> |->  Camera4CFusion ->  fusion   ->  |
               | -> decode     -> detector         -> tracker                  -> |                                    |
               |              -> radarOfflineResults ->                           |                                    | -> output
               | -> decode     -> detector         -> tracker                  -> |                                    |
               | -> decode     -> detector         -> tracker                  -> |                                    |
        input  | -> decode     -> detector         -> tracker                  -> |->  Camera4CFusion ->  fusion   ->  |
               | -> decode     -> detector         -> tracker                  -> |                                    |
               |              -> radarOfflineResults ->                           |                                    |
               | -> decode     -> detector         -> tracker                  -> |                                    |
               | -> decode     -> detector         -> tracker                  -> |                                    |
        input  | -> decode     -> detector         -> tracker                  -> |->  Camera4CFusion ->  fusion   ->  |
               | -> decode     -> detector         -> tracker                  -> |                                    |
               |              -> radarOfflineResults ->                           |                                    |
        ```

### Start Service
Open a terminal, run the following commands:

```bash
cd $PROJ_DIR
sudo bash -x run_service_bare.sh

# Output logs:
    [2023-06-26 14:34:42.970] [DualSinks] [info] MaxConcurrentWorkload sets to 1
    [2023-06-26 14:34:42.970] [DualSinks] [info] MaxPipelineLifeTime sets to 300s
    [2023-06-26 14:34:42.970] [DualSinks] [info] Pipeline Manager pool size sets to 1
    [2023-06-26 14:34:42.970] [DualSinks] [trace] [HTTP]: uv loop inited
    [2023-06-26 14:34:42.970] [DualSinks] [trace] [HTTP]: Init completed
    [2023-06-26 14:34:42.971] [DualSinks] [trace] [HTTP]: http server at 0.0.0.0:50051
    [2023-06-26 14:34:42.971] [DualSinks] [trace] [HTTP]: running starts
    [2023-06-26 14:34:42.971] [DualSinks] [info] Server set to listen on 0.0.0.0:50052
    [2023-06-26 14:34:42.972] [DualSinks] [info] Server starts 1 listener. Listening starts
    [2023-06-26 14:34:42.972] [DualSinks] [trace] Connection handle with uid 0 created
    [2023-06-26 14:34:42.972] [DualSinks] [trace] Add connection with uid 0 into the conn pool

```
> NOTE-1: workload (default as 4) can be configured in file: `$PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config`
```vim
...
[Pipeline]
maxConcurrentWorkload=4
```

> NOTE-2 : to stop service, run the following commands:
```bash
sudo pkill Hce
```


### Run Entry Program
#### 1C+1R

**The target platform is Intel® Celeron® Processor 7305E.**

All executable files are located at: $PROJ_DIR/build/bin

Usage:
```
Usage: CRSensorFusionDisplay <host> <port> <json_file> <total_stream_num> <repeats> <data_path> <display_type> [<save_flag: 0 | 1>] [<pipeline_repeats>] [<fps_window: unsigned>] [<cross_stream_num>] [<warmup_flag: 0 | 1>]  [<logo_flag: 0 | 1>]
--------------------------------------------------------------------------------
Environment requirement:
   unset http_proxy;unset https_proxy;unset HTTP_PROXY;unset HTTPS_PROXY
```
* **host**: use `127.0.0.1` to call from localhost.
* **port**: configured as `50052`, can be changed by modifying file: `$PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config` before starting the service.
* **json_file**: AI pipeline topology file.
* **total_stream_num**: to control the input streams.
* **repeats**: to run tests multiple times, so that we can get more accurate performance.
* **data_path**: multi-sensor binary files folder for input.
* **display_type**: support for `media`, `radar`, `media_radar`, `media_fusion` currently.
  * `media`: only show image results in frontview. Example:
  [![Display type: media](_images/1C1R-Display-type-media.png)](_images/1C1R-Display-type-media.png)
  * `radar`: only show radar results in birdview. Example:
  [![Display type: radar](_images/1C1R-Display-type-radar.png)](_images/1C1R-Display-type-radar.png)
  * `media_radar`: show image results in frontview and radar results in birdview separately. Example:
  [![Display type: media_radar](_images/1C1R-Display-type-media-radar.png)](_images/1C1R-Display-type-media-radar.png)
  * `media_fusion`: show both for image results in frontview and fusion results in birdview. Example:
  [![Display type: media_fusion](_images/1C1R-Display-type-media-fusion.png)](_images/1C1R-Display-type-media-fusion.png)
* **save_flag**: whether to save display results into video.
* **pipeline_repeats**: pipeline repeats number.
* **fps_window**: The number of frames processed in the past is used to calculate the fps. 0 means all frames processed are used to calculate the fps.
* **cross_stream_num**: the stream number that run in a single pipeline.
* **warmup_flag**: warm up flag before pipeline start.
* **logo_flag**: whether to add intel logo in display.

More specifically, open another terminal, run the following commands:

```bash
# multi-sensor inputs test-case
sudo -E ./build/bin/CRSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/libradar/localFusionPipeline_libradar.json 1 1 /path-to-dataset media_fusion
```
> Note: Run with `root` if users want to get the GPU utilization profiling.
> change /path-to-dataset to your data path if you generate demo data independently, or simply change it to $PROJ_DIR/ai_inference/test/demo/raddet_bin_files to use the demo data.

#### 1C+1R Unit Tests

**The target platform is Intel® Celeron® Processor 7305E.**

In this section, the unit tests of four major components will be described: media processing, radar processing, fusion pipeline without display and other tools for intermediate results.

Usage:
```
Usage: testGRPCLocalPipeline <host> <port> <json_file> <total_stream_num> <repeats> <data_path> <media_type> [<pipeline_repeats>] [<cross_stream_num>] [<warmup_flag: 0 | 1>]
--------------------------------------------------------------------------------
Environment requirement:
   unset http_proxy;unset https_proxy;unset HTTP_PROXY;unset HTTPS_PROXY
```
* **host**: use `127.0.0.1` to call from localhost.

* **port**: configured as `50052`, can be changed by modifying file: `$PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config` before starting the service.
* **json_file**: AI pipeline topology file.
* **total_stream_num**: to control the input video streams.
* **repeats**: to run tests multiple times, so that we can get more accurate performance.
* **abs_data_path**: input data, remember to use absolute data path, or it may cause error.
* **media_type**: support for `image`, `video`, `multisensor` currently.
* **pipeline_repeats**: the pipeline repeats number.
* **cross_stream_num**: the stream number that run in a single pipeline.

##### Unit Test: Media Processing
Open another terminal, run the following commands:
```bash
# media test-case
./build/bin/testGRPCLocalPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/localMediaPipeline.json 1 1 /path-to-dataset multisensor
```

#####  Unit Test: Radar Processing

Open another terminal, run the following commands:
```bash
# radar test-case
./build/bin/testGRPCLocalPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/libradar/localRadarPipeline_libradar.json 1 1 /path-to-dataset multisensor
```

##### Unit Test: Fusion pipeline without display
Open another terminal, run the following commands:
```bash
# fusion test-case
./build/bin/testGRPCLocalPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/libradar/localFusionPipeline_libradar.json 1 1 /path-to-dataset multisensor
```
#####  GPU VPLDecode test
```bash
./build/bin/testGRPCLocalPipeline 127.0.0.1 50052 ai_inference/test/configs/gpuLocalVPLDecodeImagePipeline.json 1 1000 $PROJ_DIR/_images/images image
```
#####  Media model inference visualization
```bash
./build/bin/MediaDisplay 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/localMediaPipeline.json 1 1 /path-to-dataset multisensor
```
##### Radar pipeline with radar pcl as output
```bash
./build/bin/testGRPCLocalPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/libradar/localRadarPipeline_pcl_libradar.json 1 1 /path-to-dataset multisensor
```
#####  Save radar pipeline tracking results
```bash
./build/bin/testGRPCLocalPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/libradar/localRadarPipeline_saveResult_libradar.json 1 1 /path-to-dataset multisensor
```
##### Save radar pipeline pcl results
```bash
./build/bin/testGRPCLocalPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/libradar/localRadarPipeline_savepcl_libradar.json 1 1 /path-to-dataset multisensor
```
##### Save radar pipeline clustering results
```bash
./build/bin/testGRPCLocalPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/libradar/localRadarPipeline_saveClustering_libradar.json 1 1 /path-to-dataset multisensor
```
##### Test radar pipeline performance
```bash
## no need to run the service
export HVA_NODE_DIR=$PWD/build/lib
source /opt/intel/openvino_2025/setupvars.sh
source /opt/intel/oneapi/setvars.sh
./build/bin/testRadarPerformance ai_inference/test/configs/raddet/1C1R/libradar/localRadarPipeline_libradar.json /path-to-dataset 1
```
#####  Radar pcl results visualization
```bash
./build/bin/CRSensorFusionRadarDisplay 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/libradar/localRadarPipeline_savepcl_libradar.json 1 1 /path-to-dataset pcl
```
##### Radar clustering results visualization
```bash
./build/bin/CRSensorFusionRadarDisplay 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/libradar/localRadarPipeline_saveClustering_libradar.json 1 1 /path-to-dataset clustering
```
##### Radar tracking results visualization
```bash
./build/bin/CRSensorFusionRadarDisplay 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/libradar/localRadarPipeline_libradar.json 1 1 /path-to-dataset tracking
```

#### 4C+4R

**The target platform is Intel® Core™ Ultra 7 Processor 165H.**

All executable files are located at: $PROJ_DIR/build/bin

Usage:
```
Usage: CRSensorFusion4C4RDisplay <host> <port> <json_file> <additional_json_file> <total_stream_num> <repeats> <data_path> <display_type> [<save_flag: 0 | 1>] [<pipeline_repeats>] [<cross_stream_num>] [<warmup_flag: 0 | 1>] [<logo_flag: 0 | 1>]
--------------------------------------------------------------------------------
Environment requirement:
   unset http_proxy;unset https_proxy;unset HTTP_PROXY;unset HTTPS_PROXY
```
* **host**: use `127.0.0.1` to call from localhost.
* **port**: configured as `50052`, can be changed by modifying file: `$PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config` before starting the service.
* **json_file**: AI pipeline topology file.
* **additional_json_file**: AI pipeline additional topology file.
* **total_stream_num**: to control the input streams.
* **repeats**: to run tests multiple times, so that we can get more accurate performance.
* **data_path**: multi-sensor binary files folder for input.
* **display_type**: support for `media`, `radar`, `media_radar`, `media_fusion` currently.
  * `media`: only show image results in frontview. Example:
  [![Display type: media](_images/4C4R-Display-type-media.png)](_images/4C4R-Display-type-media.png)
  * `radar`: only show radar results in birdview. Example:
  [![Display type: radar](_images/4C4R-Display-type-radar.png)](_images/4C4R-Display-type-radar.png)
  * `media_radar`: show image results in frontview and radar results in birdview separately. Example:
  [![Display type: media_radar](_images/4C4R-Display-type-media-radar.png)](_images/4C4R-Display-type-media-radar.png)
  * `media_fusion`: show both for image results in frontview and fusion results in birdview. Example:
  [![Display type: media_fusion](_images/4C4R-Display-type-media-fusion.png)](_images/4C4R-Display-type-media-fusion.png)
* **save_flag**: whether to save display results into video.
* **pipeline_repeats**: pipeline repeats number.
* **cross_stream_num**: the stream number that run in a single pipeline.
* **warmup_flag**: warm up flag before pipeline start.
* **logo_flag**: whether to add intel logo in display.

More specifically, open another terminal, run the following commands:

```bash
# multi-sensor inputs test-case
sudo -E ./build/bin/CRSensorFusion4C4RDisplay 127.0.0.1 50052 ai_inference/test/configs/raddet/4C4R/localFusionPipeline.json ai_inference/test/configs/raddet/4C4R/localFusionPipeline_npu.json 4 1 /path-to-dataset media_fusion
```
> Note: Run with `root` if users want to get the GPU utilization profiling.

To run 4C+4R with cross-stream support, for example, process 3 streams on GPU with 1 thread and the other 1 stream on NPU in another thread, run the following command:
```bash
# multi-sensor inputs test-case
sudo -E ./build/bin/CRSensorFusion4C4RDisplayCrossStream 127.0.0.1 50052 ai_inference/test/configs/raddet/4C4R/cross-stream/localFusionPipeline.json ai_inference/test/configs/raddet/4C4R/cross-stream/localFusionPipeline_npu.json 4 1 /path-to-dataset media_fusion save_flag 1 3
```

For the command above, if you encounter problems with opencv due to remote connection, you can try running the following command which sets the save flag to 2 meaning that the video will be saved locally without needing to show on the screen:
```bash
# multi-sensor inputs test-case
sudo -E ./build/bin/CRSensorFusion4C4RDisplayCrossStream 127.0.0.1 50052 ai_inference/test/configs/raddet/4C4R/cross-stream/localFusionPipeline.json ai_inference/test/configs/raddet/4C4R/cross-stream/localFusionPipeline_npu.json 4 1 /path-to-dataset media_fusion 2 1 3
```

#### 4C+4R Unit Tests

**The target platform is Intel® Core™ Ultra 7 Processor 165H.**

In this section, the unit tests of two major components will be described: fusion pipeline without display and media processing.

Usage:
```
Usage: testGRPC4C4RPipeline <host> <port> <json_file> <additional_json_file> <total_stream_num> <repeats> <data_path> [<pipeline_repeats>] [<cross_stream_num>] [<warmup_flag: 0 | 1>]
--------------------------------------------------------------------------------
Environment requirement:
   unset http_proxy;unset https_proxy;unset HTTP_PROXY;unset HTTPS_PROXY
```
* **host**: use `127.0.0.1` to call from localhost.
* **port**: configured as `50052`, can be changed by modifying file: `$PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config` before starting the service.
* **json_file**: AI pipeline topology file.
* **additional_json_file**: AI pipeline additional topology file.
* **total_stream_num**: to control the input video streams.
* **repeats**: to run tests multiple times, so that we can get more accurate performance.
* **data_path**: input data, remember to use absolute data path, or it may cause error.
* **pipeline_repeats**: pipeline repeats number.
* **cross_stream_num**: the stream number that run in a single pipeline.
* **warmup_flag**: warm up flag before pipeline start.

**Set offline radar CSV file path**
First, set the offline radar CSV file path in both localFusionPipeline.json `File location: ai_inference/test/configs/raddet/4C4R/localFusionPipeline.json` and localFusionPipeline_npu.json `File location: ai_inference/test/configs/raddet/4C4R/localFusionPipeline_npu.json` with "Configure String": "RadarDataFilePath=(STRING)/opt/radarResults.csv" like below:
```vim
{
  "Node Class Name": "RadarResultReadFileNode",
  ......
  "Configure String": "......;RadarDataFilePath=(STRING)/opt/radarResults.csv"
},
```
The method for generating offline radar files is described in [5.3.2.7 Save radar pipeline tracking results](#5327-save-radar-pipeline-tracking-results). Or you can use a pre-prepared data with the command below:
```bash
sudo cp $PROJ_DIR/ai_inference/deployment/datasets/radarResults.csv /opt
```
##### Unit Test: Fusion Pipeline without display
Open another terminal, run the following commands:
```bash
# fusion test-case
sudo -E ./build/bin/testGRPC4C4RPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/4C4R/localFusionPipeline.json ai_inference/test/configs/raddet/4C4R/localFusionPipeline_npu.json 4 1 /path-to-dataset
```

##### Unit Test: Fusion Pipeline with cross-stream without display
Open another terminal, run the following commands:
```bash
# fusion test-case
sudo -E ./build/bin/testGRPC4C4RPipelineCrossStream 127.0.0.1 50052 ai_inference/test/configs/raddet/4C4R/cross-stream/localFusionPipeline.json ai_inference/test/configs/raddet/4C4R/cross-stream/localFusionPipeline_npu.json 4 1 /path-to-dataset 1 3 
```

##### Unit Test: Media Processing
Open another terminal, run the following commands:
```bash
# media test-case
sudo -E ./build/bin/testGRPC4C4RPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/4C4R/localMediaPipeline.json ai_inference/test/configs/raddet/4C4R/localMediaPipeline_npu.json 4 1 /path-to-dataset
```

```bash
# cpu detection test-case
sudo -E ./build/bin/testGRPCLocalPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/UTCPUDetection-yoloxs.json 1 1 /path-to-dataset multisensor
```
```bash
# gpu detection test-case
sudo -E ./build/bin/testGRPCLocalPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/UTGPUDetection-yoloxs.json 1 1 /path-to-dataset multisensor
```
```bash
# npu detection test-case
sudo -E ./build/bin/testGRPCLocalPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/UTNPUDetection-yoloxs.json 1 1 /path-to-dataset multisensor
```

#### 2C+1R

**The target platform is Intel® Celeron® Processor 7305E.**

All executable files are located at: $PROJ_DIR/build/bin

Usage:

```bash
Usage: CRSensorFusion2C1RDisplay <host> <port> <json_file> <total_stream_num> <repeats> <data_path> <display_type> [<save_flag: 0 | 1>] [<pipeline_repeats>] [<fps_window: unsigned>] [<cross_stream_num>] [<warmup_flag: 0 | 1>]  [<logo_flag: 0 | 1>]
--------------------------------------------------------------------------------
Environment requirement:
   unset http_proxy;unset https_proxy;unset HTTP_PROXY;unset HTTPS_PROXY
```

* **host**: use `127.0.0.1` to call from localhost.
* **port**: configured as `50052`, can be changed by modifying file: `$PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config` before starting the service.
* **json_file**: AI pipeline topology file.
* **total_stream_num**: to control the input streams.
* **repeats**: to run tests multiple times, so that we can get more accurate performance.
* **data_path**: multi-sensor binary files folder for input.
* **display_type**: support for `media`, `radar`, `media_radar`, `media_fusion` currently.
    * `media`: only show image results in frontview. Example:
        [![Display type: media](_images/2C1R-Display-type-media.png)](_images/2C1R-Display-type-media.png)
    * `radar`: only show radar results in birdview. Example:
        [![Display type: radar](_images/2C1R-Display-type-radar.png)](_images/2C1R-Display-type-radar.png)
    * `media_radar`: show image results in frontview and radar results in birdview separately. Example:
        [![Display type: media_radar](_images/2C1R-Display-type-media-radar.png)](_images/2C1R-Display-type-media-radar.png)
    * `media_fusion`: show both for image results in frontview and fusion results in birdview. Example:
        [![Display type: media_fusion](_images/2C1R-Display-type-media-fusion.png)](_images/2C1R-Display-type-media-fusion.png)
* **save_flag**: whether to save display results into video.
* **pipeline_repeats**: pipeline repeats number.
* **fps_window**: The number of frames processed in the past is used to calculate the fps. 0 means all frames processed are used to calculate the fps.
* **cross_stream_num**: the stream number that run in a single pipeline.
* **warmup_flag**: warm up flag before pipeline start.
* **logo_flag**: whether to add intel logo in display.

More specifically, open another terminal, run the following commands:

```bash
# multi-sensor inputs test-case
sudo -E ./build/bin/CRSensorFusion2C1RDisplay 127.0.0.1 50052 ai_inference/test/configs/raddet/2C1R/localFusionPipeline_libradar.json 1 1 /path-to-dataset media_fusion
```

> Note: Run with `root` if users want to get the GPU utilization profiling.

#### 2C+1R Unit Tests

**The target platform is Intel® Celeron® Processor 7305E.**

In this section, the unit tests of three major components will be described: media processing, radar processing, fusion pipeline without display.

Usage:

```
Usage: testGRPC2C1RPipeline <host> <port> <json_file> <total_stream_num> <repeats> <data_path> <media_type> [<pipeline_repeats>] [<cross_stream_num>] [<warmup_flag: 0 | 1>]
--------------------------------------------------------------------------------
Environment requirement:
   unset http_proxy;unset https_proxy;unset HTTP_PROXY;unset HTTPS_PROXY
```

* **host**: use `127.0.0.1` to call from localhost.

* **port**: configured as `50052`, can be changed by modifying file: `$PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config` before starting the service.
* **json_file**: ai pipeline topology file.
* **total_stream_num**: to control the input video streams.
* **repeats**: to run tests multiple times, so that we can get more accurate performance.
* **abs_data_path**: input data, remember to use absolute data path, or it may cause error.
* **media_type**: support for `image`, `video`, `multisensor` currently.
* **pipeline_repeats**: the pipeline repeats number.
* **cross_stream_num**: the stream number that run in a single pipeline.



##### Unit Test: Media Processing

Open another terminal, run the following commands:

```bash
# media test-case
./build/bin/testGRPC2C1RPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/2C1R/localMediaPipeline.json 1 1 /path-to-dataset multisensor
```

##### Unit Test: Radar Processing

Open another terminal, run the following commands:

```bash
# radar test-case
./build/bin/testGRPC2C1RPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/2C1R/localRadarPipeline_libradar.json 1 1 /path-to-dataset multisensor
```

##### Unit Test: Fusion pipeline without display

Open another terminal, run the following commands:

```bash
# fusion test-case
./build/bin/testGRPC2C1RPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/2C1R/localFusionPipeline_libradar.json 1 1 /path-to-dataset multisensor
```

#### 16C+4R

**The target platform is Intel® Core™ i7-13700 and Intel® Arc™ A770 Graphics.**

All executable files are located at: $PROJ_DIR/build/bin

Usage:

```
Usage: CRSensorFusion16C4RDisplay <host> <port> <json_file> <total_stream_num> <repeats> <data_path> <display_type> [<save_flag: 0 | 1>] [<pipeline_repeats>] [<cross_stream_num>] [<warmup_flag: 0 | 1>] [<logo_flag: 0 | 1>]
--------------------------------------------------------------------------------
Environment requirement:
   unset http_proxy;unset https_proxy;unset HTTP_PROXY;unset HTTPS_PROXY
```

* **host**: use `127.0.0.1` to call from localhost.
* **port**: configured as `50052`, can be changed by modifying file: `$PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config` before starting the service.
* **json_file**: AI pipeline topology file.
* **total_stream_num**: to control the input streams.
* **repeats**: to run tests multiple times, so that we can get more accurate performance.
* **data_path**: multi-sensor binary files folder for input.
* **display_type**: support for `media`, `radar`, `media_radar`, `media_fusion` currently.
    * `media`: only show image results in frontview. Example:
        [![Display type: media](_images/16C4R-Display-type-media.png)](_images/16C4R-Display-type-media.png)
    * `radar`: only show radar results in birdview. Example:
        [![Display type: radar](_images/16C4R-Display-type-radar.png)](_images/16C4R-Display-type-radar.png)
    * `media_radar`: show image results in frontview and radar results in birdview separately. Example:
        [![Display type: media_radar](_images/16C4R-Display-type-media-radar.png)](_images/16C4R-Display-type-media-radar.png)
    * `media_fusion`: show both for image results in frontview and fusion results in birdview. Example:
        [![Display type: media_fusion](_images/16C4R-Display-type-media-fusion.png)](_images/16C4R-Display-type-media-fusion.png)
* **save_flag**: whether to save display results into video.
* **pipeline_repeats**: pipeline repeats number.
* **cross_stream_num**: the stream number that run in a single pipeline.
* **warmup_flag**: warm up flag before pipeline start.
* **logo_flag**: whether to add intel logo in display.

More specifically, open another terminal, run the following commands:

```bash
# multi-sensor inputs test-case
sudo -E ./build/bin/CRSensorFusion16C4RDisplay 127.0.0.1 50052 ai_inference/test/configs/raddet/16C4R/localFusionPipeline.json 4 1 /path-to-dataset media_fusion
```

> Note: Run with `root` if users want to get the GPU utilization profiling.

#### 16C+4R Unit Tests

**The target platform is Intel® Core™ i7-13700 and Intel® Arc™ A770 Graphics.**

In this section, the unit tests of two major components will be described: fusion pipeline without display and media processing.

Usage:

```
Usage: testGRPC16C4RPipeline <host> <port> <json_file> <total_stream_num> <repeats> <data_path> [<pipeline_repeats>] [<cross_stream_num>] [<warmup_flag: 0 | 1>]
--------------------------------------------------------------------------------
Environment requirement:
   unset http_proxy;unset https_proxy;unset HTTP_PROXY;unset HTTPS_PROXY
```

* **host**: use `127.0.0.1` to call from localhost.
* **port**: configured as `50052`, can be changed by modifying file: `$PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config` before starting the service.
* **json_file**: AI pipeline topology file.
* **total_stream_num**: to control the input video streams.
* **repeats**: to run tests multiple times, so that we can get more accurate performance.
* **data_path**: input data, remember to use absolute data path, or it may cause error.
* **pipeline_repeats**: pipeline repeats number.
* **cross_stream_num**: the stream number that run in a single pipeline.
* **warmup_flag**: warm up flag before pipeline start.

**Set offline radar CSV file path**
First, set the offline radar CSV file path in both localFusionPipeline.json `File location: ai_inference/test/configs/raddet/16C4R/localFusionPipeline.json` with "Configure String": "RadarDataFilePath=(STRING)/opt/radarResults.csv" like below:

```bash
{
  "Node Class Name": "RadarResultReadFileNode",
  ......
  "Configure String": "......;RadarDataFilePath=(STRING)/opt/radarResults.csv"
},
```

The method for generating offline radar files is described in [5.3.2.7 Save radar pipeline tracking results](#5327-save-radar-pipeline-tracking-results). Or you can use a pre-prepared data with the command below:

```bash
sudo cp $PROJ_DIR/ai_inference/deployment/datasets/radarResults.csv /opt
```

##### Unit Test: Fusion Pipeline without display

Open another terminal, run the following commands:

```bash
# fusion test-case
sudo -E ./build/bin/testGRPC16C4RPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/16C4R/localFusionPipeline.json 4 1 /path-to-dataset
```

##### Unit Test: Media Processing

Open another terminal, run the following commands:

```bash
# media test-case
sudo -E ./build/bin/testGRPC16C4RPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/16C4R/localMediaPipeline.json 4 1 /path-to-dataset
```
### KPI test

#### 1C+1R
```bash
# Run service with the following command:
sudo bash run_service_bare_log.sh
# Open another terminal, run the command below:
sudo -E ./build/bin/testGRPCLocalPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/libradar/localFusionPipeline_libradar.json 1 10 /path-to-dataset multisensor
```
Fps and average latency will be calculated.
#### 4C+4R
```bash
# Run service with the following command:
sudo bash run_service_bare_log.sh
# Open another terminal, run the command below:
sudo -E ./build/bin/testGRPC4C4RPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/4C4R/localFusionPipeline.json ai_inference/test/configs/raddet/4C4R/localFusionPipeline_npu.json 4 10 /path-to-dataset
```
Fps and average latency will be calculated.

#### 2C+1R

```bash
# Run service with the following command:
sudo bash run_service_bare_log.sh
# Open another terminal, run the command below:
sudo -E ./build/bin/testGRPC2C1RPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/2C1R/localFusionPipeline_libradar.json 1 10 /path-to-dataset multisensor
```

Fps and average latency will be calculated.

#### 16C+4R

```bash
# Run service with the following command:
sudo bash run_service_bare_log.sh
# Open another terminal, run the command below:
sudo -E ./build/bin/testGRPC16C4RPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/16C4R/localFusionPipeline.json 4 10 /path-to-dataset
```

Fps and average latency will be calculated.

### Stability test

#### 1C+1R stability test


> NOTE : change workload configuration to 1 in file: `$PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config`
```vim
...
[Pipeline]
maxConcurrentWorkload=1
```
Run the service first, and open another terminal, run the command below:
```bash
# 1C1R without display
sudo -E ./build/bin/testGRPCLocalPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/1C1R/libradar/localFusionPipeline_libradar.json 1 100 /path-to-dataset multisensor 100
```
#### 4C+4R stability test


> NOTE : change workload configuration to 4 in file: `$PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config`
```vim
...
[Pipeline]
maxConcurrentWorkload=4
```
Run the service first, and open another terminal, run the command below:
```bash
# 4C4R without display
sudo -E ./build/bin/testGRPC4C4RPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/4C4R/localFusionPipeline.json ai_inference/test/configs/raddet/4C4R/localFusionPipeline_npu.json 4 100 /path-to-dataset 100
```

#### 2C+1R stability test


> NOTE : change workload configuration to 1 in file: $PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config

```vim
...
[Pipeline]
maxConcurrentWorkload=1
```

Run the service first, and open another terminal, run the command below:

```bash
# 2C1R without display
sudo -E ./build/bin/testGRPC2C1RPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/2C1R/localFusionPipeline_libradar.json 1 100 /path-to-dataset multisensor 100
```

#### 16C+4R stability test


> NOTE : change workload configuration to 4 in file: $PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config

```vim
...
[Pipeline]
maxConcurrentWorkload=4
```

Run the service first, and open another terminal, run the command below:

```bash
# 16C4R without display
sudo -E ./build/bin/testGRPC16C4RPipeline 127.0.0.1 50052 ai_inference/test/configs/raddet/16C4R/localFusionPipeline.json 4 100 /path-to-dataset 100
```



## Build Docker image

### Install Docker Engine and Docker Compose on Ubuntu

Install [Docker Engine](https://docs.docker.com/engine/install/ubuntu/) and [Docker Compose](https://docs.docker.com/compose/) according to the guide on the official website.

Before you install Docker Engine for the first time on a new host machine, you need to set up the Docker `apt` repository. Afterward, you can install and update Docker from the repository.

1. Set up Docker's `apt` repository.

```bash
# Add Docker's official GPG key:
sudo -E apt-get update
sudo -E apt-get install ca-certificates curl
sudo -E install -m 0755 -d /etc/apt/keyrings
sudo -E curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo -E apt-get update
```

2. Install the Docker packages.

To install the latest version, run:

```bash
sudo -E apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```



3. Set proxy(Optional).

Note you may need to set proxy for docker.

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo vim /etc/systemd/system/docker.service.d/http-proxy.conf

# Modify the file contents as follows
[Service]
Environment="HTTP_PROXY=http://proxy.example.com:8080"
Environment="HTTPS_PROXY=http://proxy.example.com:8080"
Environment="NO_PROXY=localhost,127.0.0.1"
```



Then restart docker:

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```



4. Verify that the installation is successful by running the `hello-world` image:

```bash
sudo docker run hello-world
```

This command downloads a test image and runs it in a container. When the container runs, it prints a confirmation message and exits.

5. Add user to group

```bash
sudo usermod -aG docker $USER
newgrp docker
```



6. Then pull base image

```bash
docker pull ubuntu:22.04
```



### Install the corresponding driver on the host

```bash
bash install_driver_related_libs.sh
```



**If driver are already installed on the machine, you don't need to do this step.**



### Build and run docker image through scripts

> **Note that the default username is `openvino` and password is `intel` in docker image.**

##### Build and run docker image

Usage:

```bash
bash build_docker.sh <IMAGE_TAG, default tfcc:latest> <DOCKERFILE, default Dockerfile_TFCC.dockerfile>  <BASE, default ubuntu> <BASE_VERSION, default 22.04> 
```


```
bash run_docker.sh <DOCKER_IMAGE, default tfcc:latest> <NPU_ON, default false>
```

Example:

```bash
cd $PROJ_DIR/docker
bash build_docker.sh tfcc:latest Dockerfile_TFCC.dockerfile
bash run_docker.sh tfcc:latest false
# After the run is complete, the container ID will be output, or you can view it through docker ps 
```

##### Enter docker

Get the container id by command bellow:

```bash
docker ps -a
```

And then enter docker by command bellow:

```bash
docker exec -it <container id> /bin/bash
```

##### Copy dataset

If you want to copy dataset or other files to docker, you can refer the command bellow:

```bash
docker cp /path/to/dataset <container id>:/path/to/dataset
```

### Build and run docker image through docker compose

> **Note that the default username is `openvino` and password is `intel` in docker image.**

Modify `proxy`, `VIDEO_GROUP_ID` and `RENDER_GROUP_ID` in `.env` file.

```bash
# proxy settings
https_proxy=
http_proxy=
# base image settings
BASE=ubuntu
BASE_VERSION=22.04
# group IDs for various services
VIDEO_GROUP_ID=44
RENDER_GROUP_ID=110
# display settings
DISPLAY=$DISPLAY
```

You can get  `VIDEO_GROUP_ID` and `RENDER_GROUP_ID`  with the following command:

```bash
# VIDEO_GROUP_ID
echo $(getent group video | awk -F: '{printf "%s\n", $3}')
# RENDER_GROUP_ID
echo $(getent group render | awk -F: '{printf "%s\n", $3}')
```

##### Build and run docker image
Uasge:
```bash
cd $PROJ_DIR/docker
docker compose up <services-name> -d # tfcc and tfcc-npu. tfcc-npu means with NPU support
```

Example:

```bash
cd $PROJ_DIR/docker
docker compose up tfcc -d
```

Note if you need NPU support, for example, on MTL platform please run the command bellow:

```bash
cd $PROJ_DIR/docker
docker compose up tfcc-npu -d
```

##### Enter docker
Usage:
```bash
docker compose exec <services-name> /bin/bash
```
Example:
```bash
docker compose exec tfcc /bin/bash
```

##### Copy dataset

Find the container name or ID:

```bash
docker compose ps
```

Sample output:

```bash
NAME                IMAGE      COMMAND       SERVICE    CREATED         STATUS         PORTS
docker-tfcc-1    tfcc:latest   "/bin/bash"     tfcc   4 minutes ago   Up 9 seconds
```

copy dataset

```bash
docker cp /path/to/dataset docker-tfcc-1:/path/to/dataset
```

### Running inside docker

Enter the project directory `/home/openvino/metro-2.0` then run `bash -x build.sh` to build the project. Then following the guides [sec 4. How it works](#4-how-it-works) to run sensor fusion application.

## Code Reference

Some of the code is referenced from the following projects:
- [IGT GPU Tools](https://gitlab.freedesktop.org/drm/igt-gpu-tools) (MIT License)
- [Intel DL Streamer](https://github.com/dlstreamer/dlstreamer) (MIT License)
- [Open Model Zoo](https://github.com/openvinotoolkit/open_model_zoo) (Apache-2.0 License)
