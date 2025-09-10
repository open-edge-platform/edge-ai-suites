Troubleshooting
###############################################

#. **OpenVINO can't detect GPU device**

    .. code-block:: bash

        $ python3 -c "from openvino import Core; ie = Core(); print(ie.available_devices)"
        ['CPU']

    Please firstly make sure you have installed the :doc:`firmware <installation_setup/installation/gpu_firmware>` and :doc:`driver <installation_setup/installation/client_gpu_driver>` for GPU. If you are still encountering this issue:

    .. code-block:: bash

        $ export OCL_ICD_VENDORS=/etc/OpenCL/vendors

#. **MESA: warning: Driver does not support the 0x7d51 PCI ID** 

    .. code-block:: console

        MESA: warning: driver does not support the 0x7d51 PCI ID.
        DRI3 not available

    Please update mesa to fix this issue.

    .. code-block:: bash

        $ sudo apt update
        $ sudo apt install mesa-utils libgl1-mesa-dri libglx-mesa0 libigc2

#. **IPEX workloads are incompatible with the NPU driver**

    .. code-block:: console

        RuntimeError: Native API failed. Native API returns: -1102 (PI_ERROR_UNINITIALIZED) -1102 (PI_ERROR_UNINITIALIZED)

    To run IPEX workloads, please uninstall the NPU debs package installed as according to :doc:`NPU firmware <installation_setup/installation/npu_firmware>`.

    .. code-block:: bash

        $ sudo dpkg --purge --force-remove-reinstreq intel-driver-compiler-npu intel-fw-npu intel-level-zero-npu

#. **DepthAnythingV2 checkpoint download failed**

    .. _depthanythingv2_troubleshooting:

    Please modify the following download link in the script ``<Depth-Anything-ONNX_project_dir>/depth_anything_v2/config.py``.

    .. code-block:: python

        Encoder.vitb: {
            None: "https://hf-mirror.com/depth-anything/Depth-Anything-V2-Base/resolve/main/depth_anything_v2_vitb.pth?download=true",
            ..
        },

#. **OpenVINO inference failed**

    .. _ov_inference_troubleshooting:

    If you encounter some errors when running OpenVINO inference of models from :doc:`Model Tutorials <developer_tools_tutorials/model_tutorials>`, please check the OpenVINO version used for model conversion and the runtime version used for inference. The OpenVINO version used for model conversion should be the same as the runtime version used for inference. Otherwise, unexpected errors may occur, especially if the model is converted using a newer version and the runtime is an older version.

    You can check the OpenVINO version used for model conversion at the end of the OpenVINO IR file ``*.xml``. For example:

    .. code-block:: xml

        ...
         <rt_info>
                <Runtime_version value="2025.0.0-17942-1f68be9f594-releases/2025/0" />
                <conversion_parameters>
                        <framework value="pytorch" />
                        <is_python_object value="True" />
                </conversion_parameters>
        </rt_info>
        ...

#. **IOMMU deivce assigned failed when ACRN hypervisor boot up**
  
    .. code-block:: console

        failed to unassign iommu device!

    1. Please check VT-d Enabled in BIOS, refer to the BIOS configuration listed in :doc:`OS Setup <installation_setup/prerequisites/os_setup>`. 
    2. Please check all PCIe devices plugged in have been enabled correctly.

#. **Docker pull time out**

    .. _docker_proxy_troubleshooting:

    If your network environment requires proxy, please refer to the `docker documentation website <https://docs.docker.com/engine/daemon/proxy/>`_ to configure proxy settings.

#. **Performance of iGPU degrade when passthrough to VM on ACRN**

    .. _ACRN_troubleshooting:

    When passthrough the iGPU to Guest VM based on ACRN, the performance of iGPU running AI models will degrade compared to the performance on native.
