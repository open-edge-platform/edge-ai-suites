# Requirements

## Operating System

The total pipeline needs two machines, one for client and one for server.

- [Client](#environment-setup-for-windows): Windows 11 22H2 or above
- [Server](#environment-setup-for-ubuntu): Ubuntu 22.04

For 2D avatar, the [RAG](#prepare-rag) will run on the server and other parts
will run on the client.\
For 3D avatar, the RAG and lipsync
([SAiD](#prepare-project-code-and-models-on-server)) will run on the server
and the other parts will run on the client.

## Hardware

Both Windows and Ubuntu machines should be equipped with
Intel Arc A770 GPU 16GB x1.

## Environment Setup for Client (Windows)

The guide assumes the use of Visual Studio Code and Conda-forge.
However, you can use any other source code editor you prefer.

### Install Visual Studio Code and Conda-forge

Download the [Visual Studio Code installer](https://code.visualstudio.com/download)
and install the tool. Then,
[set up Git in VS Code](https://code.visualstudio.com/docs/sourcecontrol/intro-to-git#_set-up-git-in-vs-code).

Download the [Conda-forge installer](https://conda-forge.org/download/) and
install the tool. You need to add the tool to the system's PATH if you want to
use it in the VS Code terminal.

After the configuration, you can proceed with the setup, using
VS Code terminal.

### Prepare project code and models on client

Organize the project code accordingly and make sure the downloaded
third-party models are within the file structure presented below.

#### MuseTalk

1. Follow the
   [MuseTalk documentation](https://github.com/TMElyralab/MuseTalk#download-weights)
   and place all the models under the `resource/musetalk_models` directory.

   ```text
   resource/musetalk_models/
   ├── musetalk
   │   ├── musetalk.json
   │   └── pytorch_model.bin
   ├── dwpose
   │   └── dw-ll_ucoco_384.pth
   ├── face-parse-bisent
   │   ├── 79999_iter.pth
   │   └── resnet18-5c106cde.pth
   ├── sd-vae-ft-mse
   │   ├── config.json
   │   └── diffusion_pytorch_model.bin
   └── whisper
       └── tiny.pt
   ```

2. Convert the MuseTalk model to Openvino IR (Intermediate Representation):

   ```bash
   python -m da.util.musetalk_torch2ov
   ```

   After successful conversion, the Openvino IR will be saved to
   the following directory:

   ```text
   resource/musetalk_models/
   └── musetalk
       ├── unet-vae-b4.bin
       └── unet-vae-b4.xml
   ```

#### FunASR

1. Use Git to download the [FunASR](https://github.com/modelscope/FunASR)
   `speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch` model,
   used as an automatic speech recognition (ASR) model in the pipeline.

   ```bash
   cd resource/funasr_models
   git clone https://www.modelscope.cn/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch.git
   cd ../..
   ```

2. Convert the FunASR model to ONNX and apply quantization,
   using the command below:

   ```bash
   python -m da.util.funasr_torch2onnx
   ```

   After a successful conversion, the onnx quantized model will be saved to
   the following directory:

   ```text
   resource/funasr_models/
   └── speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch
       └── model.onnx
   ```

### Setup Python environment

Run the commands below to create the Python environment and install
required dependencies.

```bash
conda create --name da python=3.10 ffmpeg webrtcvad
conda activate da
pip install -r requirements.txt
mim install -r requirements-mim.txt
```

## Environment Setup for Server (Ubuntu)

### Install Docker

To install Docker, refer to the
[official website](https://docs.docker.com/engine/install/ubuntu/).

### Prepare project code and models on server

1. Organize the project code accordingly:

  - In Ubuntu, the required code should be in the `said_docker` folder.
  - [SAiD models](https://github.com/yunik1004/SAiD) are used for 3D lip sync.
    `SAiD.pth` should be placed under the `said_docker/said_models` directory:

    ```text
    said_docker
    └── said_models
        └── SAiD.pth
    ```
  - Downloaded third-party models should also be saved within a similar
    file structure.

2. Follow
   ["SAiD on A770"](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/interactive-digital-avatar/said_docker/README.md)
   to build and setup a server.

### Prepare RAG

To set up a Retrieval-Augmented Generation (RAG) pipeline, refer to
[the guide](https://github.com/opea-project/GenAIExamples/tree/main/EdgeCraftRAG).

## Learn More

- [Create interactive 2D/3D avatars](./use-cases.md)
- [SAiD: Blendshape-based Audio-Driven Speech Animation with Diffusion](https://yunik1004.github.io/SAiD/)
- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401)
