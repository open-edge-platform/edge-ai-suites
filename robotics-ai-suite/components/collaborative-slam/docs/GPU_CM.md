### GPU offload with C-for-Metal via OneAPI Level Zero

Some feature extraction operations can be offloaded to Intel GPU to free up CPU and improve overall SLAM peformance. GPU kernels can be written using OpenCL, C-for-Metal and DPC++.

Currently, we only enable GPU kernels written using [C-for-Metal](https://01.org/c-for-metal-development-package).

## Prerequisites
At first you need to figure out your Intel GPU type with the tool `lspci`. For example, the TGL platform with an integrated Intel Iris Xe GPU can have below output.
```
lspci -v | grep -A10 VGA
0000:00:02.0 VGA compatible controller: Intel Corporation Device 9a49 (rev 03) (prog-if 00 [VGA controller])
        DeviceName: Onboard - Video
        Subsystem: Dell Device 0afc
        Flags: bus master, fast devsel, latency 0, IRQ 206
        Memory at 6054000000 (64-bit, non-prefetchable) [size=16M]
        Memory at 4000000000 (64-bit, prefetchable) [size=256M]
        I/O ports at 3000 [size=64]
        Expansion ROM at 000c0000 [virtual] [disabled] [size=128K]
        Capabilities: <access denied>
        Kernel driver in use: i915
        Kernel modules: i915
```
Second, you need to follow [specific instructions](https://dgpu-docs.intel.com/installation-guides/index.html) to install necessary software packages based on the GPU type. For example, as for the above integrated Intel GPU, it belongs to the Intel Gen12/DG1 GPU. The final step is to configure the permissions for your user account, the related commands are also listed in the above link.
After successfully installing all the packages, you are able to use `sycl-ls` (comes with oneAPI package) to verify that LevelZero is ready and exposed. You should see the line below in the output.
```
[level_zero:0] GPU : Intel(R) Level-Zero 1.3 [1.3.23405]
```
Or `clinfo` command (use `sudo apt install clinfo` to install) to verify the environment, you should see the similar output as below.
```
clinfo | grep -A3 "Number of devices"
Number of devices                                 1
  Device Name                                     Intel(R) Iris(R) Xe Graphics [0x9a49]
  Device Vendor                                   Intel(R) Corporation
  Device Vendor ID                                0x8086
```
Third, you need to download the [C-for-Metal](https://www.intel.com/content/www/us/en/developer/tools/open/c-for-metal-sdk/overview.html) package and the latest orb-extractor library. In most of the cases, orb-extractor package is enough for Collaborative SLAM to run. But if you want to compile orb-extractor library from source, please follow instructions provided in the [orb-extractor repo](https://github.com/open-edge-platform/edge-ai-libraries/libraries/orb-extractor). You can specify custom install directory by using `CMAKE_INSTALL_PREFIX`.

### Troubleshooting

User must be member of `sudo` or `root` groups. Run `groups` to very this.

If you are running within the docker, make sure `--group-add render` option is added when starting
a docker. In case of EI for AMR docker, run:
```
 ./run_interactive_docker.sh <docker_image> eiforamr -e "--group-add render"
```

## Build

To get Collaborative SLAM with C-for-Metal GPU support, make sure that Prerequisites are done.
If so, then simply run:
```
colcon build --cmake-args -DUSE_GPU_CM=1 -DCM_GPU_INSTALL_DIR=/path/to/orb_extractor/install/dir
```

### Troubleshooting

In case build fails due to missing `catkin_pkg` or some other package, check if proper
python version is used. Due to sourcing oneAPI env, which comes with its own python interpreter, it
might not have all python packages as default system python executable has.

To solve this, add `cmake` arg `PYTHON_EXECUTABLE` specifying python interpreter. Example:
```
colcon build --cmake-args -DUSE_GPU_CM=1 -DCM_GPU_INSTALL_DIR=/path/to/orb_extractor/install/dir -DPYTHON_EXECUTABLE:FILEPATH=/usr/bin/python3
```

## Run

In order to run the Collaborative SLAM with GPU support, one should first source the C-for-Metal env, then source the workspace env (the order of env sourcing is important) and finally specify the `LD_LIBRARY_PATH`.
```
cd /path/to/c-for-metal/sdk/
source setupenv.sh
cd /path/to/ros2-workspace/
source install/setup.bash
export LD_LIBRARY_PATH=/path/to/orb_extractor/install/dir/lib:$LD_LIBRARY_PATH
# Run the tracker
```
