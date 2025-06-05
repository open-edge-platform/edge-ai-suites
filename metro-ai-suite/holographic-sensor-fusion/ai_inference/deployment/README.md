> ## How to build AI inference docker.
> Assume current folder is deployment, to successful compile AI inference docker, the following file is needed:
>>      + build_hce_core.sh
>>      + replacePrefix.py
>>      + run_service.sh
>>      + build_binary_from_source.dockerfile
>>      + build_binary_from_source.sh
>>      + build_image_from_binary.sh
>>      + ../deploymentFromBinary/build_hce_core.sh
>>      + ../deploymentFromBinary/run_service.sh
>>      + ../deploymentFromBinary/build_image_from_binary.dockerfile
> And the dev machine must install docker and already have a hddlunite-image:GROUP1.0 image which contains keenbay >  related environment, and developer need create a release_dir folder which contains related lib and modles, the directory must as follows:
release_dir/
├── Core_services
│   └── Storage
│       └── Feature_storage
│           └── libfeature_storage.so
└── models
    ├── test_reid_model_int8_U8U8.blob
    └── yolo-v2-tiny-ava-0001.blob

> Here is the detailed steps:
> 1. Checkout the latest hce-core code: 
>>      'git clone https://gitlab.devtools.intel.com/hce/hce-core.git'
> 2. Enter dirextory middleware/ai/ai_inference/deployment/
>>      'cd middleware/ai/ai_inference/deployment/'
> 3. Set environemnt variable for running script.
>>      export RELEASE_ROOT=/path/to/release_dir
>>      export http_proxy="http://http_proxy_ip:port/"
>>      export https_proxy="http://http_proxy_ip:port/"
> 4. Execute script.
>>      ./build_binary_from_source.sh
> 5. Check release binary in $release_dir/Core_services/AI/Ai_inference/binary

> ## How to build AI inference docker image from binary using script.
> 1. Set environemnt variable for running script.
>>      export RELEASE_ROOT=/path/to/release_dir
>>      export http_proxy="http://http_proxy_ip:port/"
>>      export https_proxy="http://http_proxy_ip:port/"
> 2. Enter release folder.
>>      'cd $RELEASE_ROOT/Core_services/AI/Ai_inference/binary'
> 3. Execute script.
>>      ./build_image_from_binary.sh
> And you can find release image in $release_dir/Core_services/AI
