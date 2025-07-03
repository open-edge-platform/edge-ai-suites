# Requirements

## Operating System

The total pipeline needs two machines, one for client and one for server. 

- Windows 11 22H2 or above for client.
- Ubuntu 22.04 for server. 

For 2D avatar, the RAG will run on server and other parts will run on client.
For 3D avatar, the RAG and lipsync (SAiD) will run on server and the other parts will run on client.

## Hardware

- Windows: Intel Arc A770 GPU 16GB x1
- Ubuntu: Intel Arc A770 GPU 16GB x1

# Environment setup for windows

Please use the tools you are familiar with. Here we take Visual Studio Code and Conda-forge as an example.

## Install Visual Studio Code and Conda-forge

Download the Visual Studio Code installer from [official website](https://code.visualstudio.com/download) and install the tool. Please refer to this [guide](https://code.visualstudio.com/docs/sourcecontrol/intro-to-git) for the Git configuration.

Download the Conda-forge installer from [official website](https://conda-forge.org/download/) and install the tool. The tool also needs to be added to system's PATH if you want to use it in the Visual Studio Code terminal.

After the configuration, you should be able to finish most of the setup steps through Visual Studio Code terminal.

## Prepare project code and models

Put the project code in the appropriate directory. Download the third-party models and organize them according to the following structure.

### MuseTalk

Please follow [MuseTalk doc](https://github.com/TMElyralab/MuseTalk#download-weights). Put all models under dir
`resource/musetalk_models`.

```
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

Convert museTalk to openvino:

```
python -m da.util.musetalk_torch2ov
```

The openvino model should be saved to following dir if convertion success.

```
resource/musetalk_models/
└── musetalk
    ├── unet-vae-b4.bin
    └── unet-vae-b4.xml
```

### FunASR

We use `speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch` model as ASR model in pipeline.
Download model via git:

```bash
cd resource/funasr_models
git clone https://www.modelscope.cn/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch.git
cd ../..
```

To convert model to onnx and apply quantization:

```bash
python -m da.util.funasr_torch2onnx
```

The onnx quantization model should be saved to following dir if convertion success.

```
resource/funasr_models/
└── speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch
    └── model.onnx
```

## Setup Python env

In the terminal, execute the following commands:

```bash
conda create --name da python=3.10 ffmpeg webrtcvad
conda activate da
pip install -r requirements.txt
mim install -r requirements-mim.txt
```

# Environment setup for Ubuntu

## Install docker

Please refer to the [official website](https://docs.docker.com/engine/install/ubuntu/) to install the docker. 

## Prepare project code and models

Put the project code in the appropriate directory. In the Ubuntu, the code we need is in the said_docker folder.

Download the third-party models and organize them according to the following structure.

### SAiD

We use SAiD for 3D lip sync. Put `SAiD.pth` under dir `said_docker/said_models`.

```
said_docker
└── said_models
    └── SAiD.pth
```

And follow [SAiD README.md](../said_docker/README.md) to build and setup said server.

## Prepare RAG

Please refer to [this guide](https://github.com/opea-project/GenAIExamples/tree/main/EdgeCraftRAG) to set up RAG.
