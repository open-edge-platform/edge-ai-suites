# Get Started Guide

## Run Metro AI Suite Sensor Fusion for Traffic Management Application on Bare Metal systems

In this section, we describe how to run Metro AI Suite Sensor Fusion for Traffic Management application on Bare Metal systems.

For prerequisites and system requirements, see [prerequisites.md](./prerequisites.md) and [system-req.md](./system-req.md).

Metro AI Suite Sensor Fusion for Traffic Management application can support different pipeline using topology JSON files to describe the pipeline topology. The defined pipeline topology can be found at [Resources Summary](#resources-summary)

There are two steps required for running the sensor fusion application:
- Start AI Inference service, more details can be found at [Start Service](#start-service)
- Run the application entry program, more details can be found at [Run Entry Program](#run-entry-program)

Besides, you can test each component (without display) following the guides at [Advanced-User-Guide.md](./advanced-user-guide.md#entry-program)

### Resources Summary
- Local File Pipeline for Media pipeline
  - Json File: localMediaPipeline.json 
    
    > File location: `$PROJ_DIR/ai_inference/test/configs/kitti/1C1L/localMediaPipeline.json`
  - Pipeline Description: 
    ```
    input -> decode -> detection -> tracking -> output
    ```
  
- Local File Pipeline for Lidar pipeline
  - Json File: localLidarPipeline.json
    
    > File location: `$PROJ_DIR/ai_inference/test/configs/kitti/1C1L/localLidarPipeline.json`
- Pipeline Description: 
  
    ```
    input -> lidar signal processing -> output
  ```
  
- Local File Pipeline for `Camera + Lidar(2C+1L)` Sensor fusion pipeline

  - Json File: localFusionPipeline.json
    
    > File location: `$PROJ_DIR/ai_inference/test/configs/kitti/2C1L/localFusionPipeline.json`
  - Pipeline Description: 
    ```
           | -> decode     -> detector         -> tracker                  -> |                                    |
    input  | -> decode     -> detector         -> tracker                  -> | -> LidarCam2CFusion ->  fusion  -> | -> output
           | ->                lidar signal processing                     -> |                                    |
    ```
- Local File Pipeline for `Camera + Lidar(4C+2L)` Sensor fusion pipeline

  - Json File: localFusionPipeline.json
    
    > File location: `$PROJ_DIR/ai_inference/test/configs/raddet/2C1L/localFusionPipeline.json`
  - Pipeline Description: 
    ```
           | -> decode     -> detector         -> tracker                  -> |                                    |
    input  | -> decode     -> detector         -> tracker                  -> | -> LidarCam2CFusion ->  fusion  -> |
           | ->                lidar signal processing                     -> |                                    |
           | -> decode     -> detector         -> tracker                  -> |                                    | -> output
    input  | -> decode     -> detector         -> tracker                  -> | -> LidarCam2CFusion ->  fusion  -> | 
           | ->                lidar signal processing                     -> |                                    |
    ```
  
- Local File Pipeline for `Camera + Lidar(12C+2L)` Sensor fusion pipeline

    - Json File: localFusionPipeline.json
      `File location: ai_inference/test/configs/kitti/6C1L/localFusionPipeline.json`

    - Pipeline Description: 

        ```
               | -> decode     -> detector         -> tracker                  -> |                                    |
               | -> decode     -> detector         -> tracker                  -> |                                    |
               | -> decode     -> detector         -> tracker                  -> |                                    |
        input  | -> decode     -> detector         -> tracker                  -> | ->  LidarCam6CFusion -> fusion  -> | -> output
               | -> decode     -> detector         -> tracker                  -> |                                    |
               | -> decode     -> detector         -> tracker                  -> |                                    |
               | ->                lidar signal processing                     -> |                                    |
        ```

- Local File Pipeline for `Camera + Lidar(8C+4L)` Sensor fusion pipeline

    - Json File: localFusionPipeline.json
      `File location: ai_inference/test/configs/kitti/2C1L/localFusionPipeline.json`

    - Pipeline Description: 

        ```
               | -> decode     -> detector         -> tracker                  -> |                                    |
        input  | -> decode     -> detector         -> tracker                  -> | -> LidarCam2CFusion ->  fusion  -> |
               | ->                lidar signal processing                     -> |                                    |
               | -> decode     -> detector         -> tracker                  -> |                                    |
        input  | -> decode     -> detector         -> tracker                  -> | -> LidarCam2CFusion ->  fusion  -> | 
               | ->                lidar signal processing                     -> |                                    | -> output
               | -> decode     -> detector         -> tracker                  -> |                                    |
        input  | -> decode     -> detector         -> tracker                  -> | -> LidarCam2CFusion ->  fusion  -> | 
               | ->                lidar signal processing                     -> |                                    |
               | -> decode     -> detector         -> tracker                  -> |                                    |
        input  | -> decode     -> detector         -> tracker                  -> | -> LidarCam2CFusion ->  fusion  -> | 
               | ->                lidar signal processing                     -> |                                    |
        ```
  
- Local File Pipeline for `Camera + Lidar(12C+4L)` Sensor fusion pipeline

    - Json File: localFusionPipeline.json
      `File location: ai_inference/test/configs/kitti/3C1L/localFusionPipeline.json`

    - Pipeline Description: 

        ```
               | -> decode     -> detector         -> tracker                  -> |                                    |
               | -> decode     -> detector         -> tracker                  -> |                                    |
        input  | -> decode     -> detector         -> tracker                  -> | ->  LidarCam3CFusion -> fusion  -> | -> output
               | ->                lidar signal processing                     -> |                                    |
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
> NOTE-1 : workload (default as 4) can be configured in file: `$PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config`
```
...
[Pipeline]
maxConcurrentWorkload=4
```

> NOTE-2 : to stop service, run the following commands:
```bash
sudo pkill Hce
```

### Run Entry Program

#### Usage

All executable files are located at: $PROJ_DIR/build/bin

##### entry program with display

```
Usage: CLSensorFusionDisplay <host> <port> <json_file> <total_stream_num> <repeats> <data_path> <display_type> <visualization_type>    [<save_flag: 0 | 1>] [<pipeline_repeats>] [<cross_stream_num>] [<warmup_flag: 0 | 1>] [<logo_flag: 0 | 1>]
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
* **display_type**: support for `media`, `lidar`, `media_lidar`, `media_fusion` currently.
  * `media`: only show image results in frontview.
  * `lidar`: only show lidar results in birdview.
  * `media_lidar`: show image results in frontview and lidar results in birdview separately.
  * `media_fusion`: show both for image results in frontview and fusion results in birdview.
* **visualization_type**: visualization type of different pipelines, currently support `2C1L`, `4C2L`, `8C4L`, `12C2L`.
* **save_flag**: whether to save display results into video.
* **pipeline_repeats**: pipeline repeats number.
* **cross_stream_num**: the stream number that run in a single pipeline.
* **warmup_flag**: warm up flag before pipeline start.
* **logo_flag**: whether to add intel logo in display.


#### 2C+1L

**The target platform is Intel® Core™ Ultra 7 265H.**

> Note: Run with `root` if users want to get the GPU utilization profiling.
> change /path-to-dataset to your data path.

Please refer to [kitti360_guide.md](../../deployments/how_to_generate_kitti_format_dataset/kitti360_guide.md) for data preparation, or just use demo data in [kitti360](../../ai_inference/test/demo/kitti360/).

- `media_fusion` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localFusionPipeline.json 1 1 /path-to-dataset media_fusion 2C1L
    ```

    ![Display type: media_fusion](_images/2C1L-Display-type-media-fusion.png)

- `media_lidar` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localFusionPipeline.json 1 1 /path-to-dataset media_lidar 2C1L
    ```

    ![Display type: media_lidar](_images/2C1L-Display-type-media-lidar.png)

- `media` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localMediaPipeline.json 1 1 /path-to-dataset media 2C1L
    ```

    ![Display type: media](_images/2C1L-Display-type-media.png)

- `lidar` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localLidarPipeline.json 1 1 /path-to-dataset lidar 2C1L
    ```

    ![Display type: lidar](_images/2C1L-Display-type-lidar.png)

#### 4C+2L

**The target platform is Intel® Core™ Ultra 7 265H.**

> Note: Run with `root` if users want to get the GPU utilization profiling.
> change /path-to-dataset to your data path.

Please refer to [kitti360_guide.md](../../deployments/how_to_generate_kitti_format_dataset/kitti360_guide.md) for data preparation, or just use demo data in [kitti360](../../ai_inference/test/demo/kitti360/).

- `media_fusion` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localFusionPipeline.json 2 1 /path-to-dataset media_fusion 4C2L
    ```

    ![Display type: media_fusion](_images/4C2L-Display-type-media-fusion.png)

- `media_lidar` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localFusionPipeline.json 2 1 /path-to-dataset media_lidar 4C2L
    ```

    ![Display type: media_lidar](_images/4C2L-Display-type-media-lidar.png)

- `media` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localMediaPipeline.json 2 1 /path-to-dataset media 4C2L
    ```

    ![Display type: media](_images/4C2L-Display-type-media.png)

- `lidar` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localLidarPipeline.json 2 1 /path-to-dataset lidar 4C2L
    ```

    ![Display type: lidar](_images/4C2L-Display-type-lidar.png)

#### 12C+2L

**Intel® Core™ i7-13700 and Intel® B580 Graphics.**

> Note: Run with `root` if users want to get the GPU utilization profiling.
> change /path-to-dataset to your data path.

Please refer to [kitti360_guide.md](../../deployments/how_to_generate_kitti_format_dataset/kitti360_guide.md) for data preparation, or just use demo data in [kitti360](../../ai_inference/test/demo/kitti360/).

- `media_fusion` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/6C1L/localFusionPipeline.json 2 1 /path-to-dataset media_fusion 12C2L
    ```

    ![Display type: media_fusion](_images/12C2L-Display-type-media-fusion.png)

- `media_lidar` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/6C1L/localFusionPipeline.json 2 1 /path-to-dataset media_lidar 12C2L
    ```

    ![Display type: media_lidar](_images/12C2L-Display-type-media-lidar.png)

- `media` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/6C1L/localMediaPipeline.json 2 1 /path-to-dataset media 12C2L
    ```

    ![Display type: media](_images/12C2L-Display-type-media.png)

- `lidar` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/6C1L/localLidarPipeline.json 2 1 /path-to-dataset lidar 12C2L
    ```

    ![Display type: lidar](_images/12C2L-Display-type-lidar.png)

#### 8C+4L

**Intel® Core™ i7-13700 and Intel® B580 Graphics.**

> Note: Run with `root` if users want to get the GPU utilization profiling.
> change /path-to-dataset to your data path.

Please refer to [kitti360_guide.md](../../deployments/how_to_generate_kitti_format_dataset/kitti360_guide.md) for data preparation, or just use demo data in [kitti360](../../ai_inference/test/demo/kitti360/).

- `media_fusion` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localFusionPipeline.json 4 1 /path-to-dataset media_fusion 8C4L
    ```

    ![Display type: media_fusion](_images/8C4L-Display-type-media-fusion.png)

- `media_lidar` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localFusionPipeline.json 4 1 /path-to-dataset media_lidar 8C4L
    ```

    ![Display type: media_lidar](_images/8C4L-Display-type-media-lidar.png)

- `media` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localMediaPipeline.json 4 1 /path-to-dataset media 8C4L
    ```

    ![Display type: media](_images/8C4L-Display-type-media.png)

- `lidar` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localLidarPipeline.json 4 1 /path-to-dataset lidar 8C4L
    ```

    ![Display type: lidar](_images/8C4L-Display-type-lidar.png)

#### 12C+4L

**Intel® Core™ i7-13700 and Intel® B580 Graphics.**

> Note: Run with `root` if users want to get the GPU utilization profiling.
> change /path-to-dataset to your data path.

Please refer to [kitti360_guide.md](../../deployments/how_to_generate_kitti_format_dataset/kitti360_guide.md) for data preparation, or just use demo data in [kitti360](../../ai_inference/test/demo/kitti360/).

- `media_fusion` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/3C1L/localFusionPipeline.json 4 1 /path-to-dataset media_fusion 12C4L
    ```

    ![Display type: media_fusion](_images/12C4L-Display-type-media-fusion.png)

- `media_lidar` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/3C1L/localFusionPipeline.json 4 1 /path-to-dataset media_lidar 12C4L
    ```

    ![Display type: media_lidar](_images/12C4L-Display-type-media-lidar.png)

- `media` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/3C1L/localMediaPipeline.json 4 1 /path-to-dataset media 12C4L
    ```

    ![Display type: media](_images/12C4L-Display-type-media.png)

- `lidar` display type

    open another terminal, run the following commands:

    ```bash
    # multi-sensor inputs test-case
    sudo -E ./build/bin/CLSensorFusionDisplay 127.0.0.1 50052 ai_inference/test/configs/kitti/3C1L/localLidarPipeline.json 4 1 /path-to-dataset lidar 12C4L
    ```

    ![Display type: lidar](_images/12C4L-Display-type-lidar.png)


## Run Metro AI Suite Sensor Fusion for Traffic Management Application on EMT systems

This section explains how to run Sensor Fusion for Traffic Management on EMT systems.

For prerequisites and system requirements, please prepare a machine with the EMT system installed.

**For EMT systems, Sensor Fusion for Traffic Management is only available in containerized format. To deploy and run the application on EMT, please follow the guidance bellow for pulling the docker image from DockerHub and running the containerized application.**

### Install X11

```bash
sudo -E tdnf install xorg-x11-server-Xorg xorg-x11-xinit xorg-x11-xinit-session xorg-x11-drv-libinput xorg-x11-apps xterm openbox libXfont2 freefont freetype gtk3 qemu-with-ui  
sudo dnf install python3
sudo -E python3 -m pip install PyXDG 
```

### Modify 20-modesetting.conf

```bash
cd /usr/share/X11/xorg.conf.d/
sudo nano 20-modesetting.conf

## Add the following configuration into 20-modesetting.conf
Section "Device"
  Identifier "Intel_Graphics"
    Driver "modesetting"
    Option "SWcursor" "true"
    Option "AccelMethod" "glamor"
    Option "DRI" "3"
EndSection
```

### X11 setting

```bash
export XDG_RUNTIME_DIR=/tmp
sudo -E bash -c 'xinit /usr/bin/openbox-session &'

export DISPLAY=:0
xhost +

xhost +local:docker
```

### Pull docker image

You can pull latest tfcc docker image through [intel/tfcc - Docker Image](https://hub.docker.com/r/intel/tfcc/).

For example:

```bash
docker pull intel/tfcc:latest
```

### Run TFCC docker image on EMT systems

For EMT systems, Sensor Fusion for Traffic Management is only available in containerized format. To deploy and run the application on EMT, please pulling the docker image from DockerHub and follow the guidance in the [run docker image](./advanced-user-guide.md#run-docker-image) section and [Running inside docker](./advanced-user-guide.md#running-inside-docker) section of [Advanced-User-Guide.md](./advanced-user-guide.md).



## Code Reference

Some of the code is referenced from the following projects:
- [IGT GPU Tools](https://gitlab.freedesktop.org/drm/igt-gpu-tools) (MIT License)
- [Intel DL Streamer](https://github.com/dlstreamer/dlstreamer) (MIT License)
- [Open Model Zoo](https://github.com/openvinotoolkit/open_model_zoo) (Apache-2.0 License)



## Troubleshooting

1. If you run different pipelines in a short period of time, you may encounter the following error:
    ![workload_error](./_images/workload_error.png)

    <center>Figure 1: Workload constraints error</center>

    This is because the maxConcurrentWorkload limitation in `AiInference.config` file. If the workloads hit the maximum, task will be canceled due to workload constrains. To solve this problem, you can kill the service with the following commands, and re-execute the command.

    ```bash
    sudo pkill Hce
    ```

2. If you encounter the following error during code compilation, it is because mkl is not installed successfully:
    ![mkl_error](./_images/mkl_error.png)

    <center>Figure 2: Build failed due to mkl error</center>

    Run `ls /opt/intel` to check if there is a OneAPI directory in the output. If not, it means that mkl was not installed successfully. You need to reinstall mkl by following the steps below:

    ```bash
    curl -k -o GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB -L
    sudo -E apt-key add GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB && sudo rm GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB
    echo "deb https://apt.repos.intel.com/oneapi all main" | sudo tee /etc/apt/sources.list.d/oneAPI.list
    sudo -E apt-get update -y
    sudo -E apt-get install -y intel-oneapi-mkl-devel lsb-release
    ```

3. If the system time is incorrect, you may encounter the following errors during installation:
    ![oneapi_time_error](./_images/oneapi_time_error.png)

    <center>Figure 3: System Time Error</center>

    You need to set the correct system time, for example:

    ```bash
    sudo timedatectl set-ntp true
    ```

    Then re-run the above installation command.

    ```bash
    sudo apt-get remove --purge intel-oneapi-mkl-devel
    sudo apt-get autoremove -y
    sudo apt-get install -y intel-oneapi-mkl-devel
    ```

4. If you encounter the following errors during running on B580 platform:
    ![device_index_error](./_images/device_index_error.png)

    <center>Figure 4: Device Index Error</center>

    It may be because the iGPU is not enabled, only the B580 is enabled.

    You can use `lspci | grep VGA` to view the number of GPU devices on the machine.
    
    The solution is either enable iGPU in BIOS, or change the config of `Device=(STRING)GPU.1` to `Device=(STRING)GPU` in `VPLDecoderNode` and `VPLDecoderNode` in pipeline config file, for example: `ai_inference/test/configs/kitti/6C1L/localFusionPipeline.json`.

5. If you encounter the following backends mismatch errors during running pipeline:
    ![backends_mismatch_error](./_images/backends_mismatch_error.png)
    
    <center>Figure 5: Backends Mismatch Error</center>
    
    This is because the wrong or non-existent device is selected. We need to select the `dGPU+opencl` Backend. As shown in the figure, it should be the second device (numbered starting from 0), that is, `GPU.2`.
    
    The solution is change config `Device=(STRING)GPU.4` to `Device=(STRING)GPU.2` in `LidarSignalProcessingNode` in pipeline config file, for example:  `ai_inference/test/configs/kitti/6C1L/localFusionPipeline.json`.




Current Version: 3.0
- Support 2C+1L/4C+2L pipeline
- Support 8C+4L/12C+2L pipeline
- Support Pointpillar model
- Updated OpenVINO to 2025.3
- Updated oneAPI to 2025.3.0

