# Troubleshooting

## Quick Navigation

- [Humanoid Imitation Learning](#humanoid_embodied_troubleshooting)
- [Stationary Robot Vision & Control](#rvc_troubleshooting)

(humanoid_embodied_troubleshooting)=
## Humanoid Imitation Learning

1. **OpenVINO can't detect GPU device**

   ```bash
   python3 -c "from openvino import Core; ie = Core(); print(ie.available_devices)"
   ['CPU']
   ```

   Please firstly make sure you have installed the [firmware](embodied/get-started/installation/gpu_firmware.rst) and [driver](embodied/get-started/installation/client_gpu_driver.rst) for GPU. If you are still encountering this issue:

   ```bash
   export OCL_ICD_VENDORS=/etc/OpenCL/vendors
   ```

2. **MESA: warning: Driver does not support the 0x7d51 PCI ID**

   ```console
   MESA: warning: driver does not support the 0x7d51 PCI ID.
   DRI3 not available
   ```

   Please update mesa to fix this issue.

   ```bash
   sudo apt update
   sudo apt install mesa-utils libgl1-mesa-dri libglx-mesa0 libigc2
   ```

3. **IPEX workloads are incompatible with the NPU driver**

   ```console
   RuntimeError: Native API failed. Native API returns: -1102 (PI_ERROR_UNINITIALIZED) -1102 (PI_ERROR_UNINITIALIZED)
   ```

   To run IPEX workloads, please uninstall the NPU debs package installed as according to [NPU firmware](embodied/get-started/installation/npu_firmware.rst).

   ```bash
   sudo dpkg --purge --force-remove-reinstreq intel-driver-compiler-npu intel-fw-npu intel-level-zero-npu
   ```

4. **DepthAnythingV2 checkpoint download failed**

   (depthanythingv2_troubleshooting)=

   Please modify the following download link in the script `<Depth-Anything-ONNX_project_dir>/depth_anything_v2/config.py`.

   ```python
   Encoder.vitb: {
       None: "https://hf-mirror.com/depth-anything/Depth-Anything-V2-Base/resolve/main/depth_anything_v2_vitb.pth?download=true",
       ..
   },
   ```

5. **OpenVINO inference failed**

   (ov_inference_troubleshooting)=

   If you encounter some errors when running OpenVINO inference of models from [Model Tutorials](embodied/model_tutorials.md), please check the OpenVINO version used for model conversion and the runtime version used for inference. The OpenVINO version used for model conversion should be the same as the runtime version used for inference. Otherwise, unexpected errors may occur, especially if the model is converted using a newer version and the runtime is an older version.

   You can check the OpenVINO version used for model conversion at the end of the OpenVINO IR file `*.xml`. For example:

   ```xml
   ...
    <rt_info>
           <Runtime_version value="2025.0.0-17942-1f68be9f594-releases/2025/0" />
           <conversion_parameters>
                   <framework value="pytorch" />
                   <is_python_object value="True" />
           </conversion_parameters>
   </rt_info>
   ...
   ```

6. **IOMMU device assigned failed when ACRN hypervisor boot up**

   ```console
   failed to unassign iommu device!
   ```

   1. Please check VT-d Enabled in BIOS, refer to the BIOS configuration listed in [OS Setup](embodied/get-started/prerequisites/os_setup.rst).

   2. Please check all PCIe devices plugged in have been enabled correctly.

7. **Docker pull time out**

   (docker_proxy_troubleshooting)=

   If your network environment requires proxy, please refer to the [docker documentation website](https://docs.docker.com/engine/daemon/proxy/) to configure proxy settings.

8. **Performance of iGPU degrade when passthrough to VM on ACRN**

   (ACRN_troubleshooting)=

   When passthrough the iGPU to Guest VM based on ACRN, the performance of iGPU running AI models will degrade compared to the performance on native.

(rvc_troubleshooting)=
## Stationary Robot Vision & Control

1. Inference on GPU does not work?

   ```bash
   sudo -E apt install clinfo
   clinfo
   ```

   Verify that the GPU is part of supported platforms:

   ```text
   Number of platforms                             1
   Platform Name                                   Intel(R) OpenCL HD Graphics
   Platform Vendor                                 Intel(R) Corporation
   Platform Version                                OpenCL 3.0
   Platform Profile                                FULL_PROFILE
   ```

2. Robot does not move?

   First start the motion controller, then press play on the pendant.

3. Robot arm does not go accurately pick up the object?

   Check [Camera pose calibration](rvc/use_cases/dynamic_use_case/system_config.rst#camera_integration)
