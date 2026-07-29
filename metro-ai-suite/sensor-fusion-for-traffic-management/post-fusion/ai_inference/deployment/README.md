# How to build AI inference docker

Assume the current folder is `deployment`. For successful compilation of AI inference docker, the following files are needed:

- build_hce_core.sh
- replacePrefix.py
- run_service.sh
- build_binary_from_source.dockerfile
- build_binary_from_source.sh
- build_image_from_binary.sh
- ../deploymentFromBinary/build_hce_core.sh
- ../deploymentFromBinary/run_service.sh
- ../deploymentFromBinary/build_image_from_binary.dockerfile

 And the dev machine must install docker and already have a `hddlunite-image:GROUP1.0` image which contains keenbay >  related environment, and you need to create the `release_dir` folder which contains related libs and models. The directory must be as follows:

 ```text
 release_dir/
 ├── Core_services
 │   └── Storage
 │       └── Feature_storage
 │           └── libfeature_storage.so
 └── models
     ├── test_reid_model_int8_U8U8.blob
     └── yolo-v2-tiny-ava-0001.blob
 ```

1. Checkout to the latest hce-core code.

   ```bash
   git clone https://gitlab.devtools.intel.com/hce/hce-core.git
   ```

2. Enter the `middleware/ai/ai_inference/deployment/` directory.

   ```bash
   cd middleware/ai/ai_inference/deployment/
   ```

3. Set the environment variables for running the script below.

   ```bash
   export RELEASE_ROOT=/path/to/release_dir
   export http_proxy="http://http_proxy_ip:port/"
   export https_proxy="http://http_proxy_ip:port/"
   ```

4. Execute the script.

   ```bash
   ./build_binary_from_source.sh
   ```

5. Check release binary in `$release_dir/Core_services/AI/Ai_inference/binary`

## How to build AI inference docker image from binary using script

1. Set the environment variables for running the script below.

   ```bash
   export RELEASE_ROOT=/path/to/release_dir
   export http_proxy="http://http_proxy_ip:port/"
   export https_proxy="http://http_proxy_ip:port/"
   ```

2. Enter the release folder.

   ```bash
   cd $RELEASE_ROOT/Core_services/AI/Ai_inference/binary
   ```

3. Execute the script.

   ```bash
   ./build_image_from_binary.sh
   ```

   You can find the release image in `$release_dir/Core_services/AI`.
