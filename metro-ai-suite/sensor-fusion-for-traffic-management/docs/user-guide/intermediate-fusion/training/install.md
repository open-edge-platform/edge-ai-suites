# Step-by-step installation instructions

## 1. Configuring the BEVFusion runtime environment

Follow the [the official configuration guide](https://github.com/mit-han-lab/bevfusion#prerequisites).

## 2. Install additional python dependency libraries

```bash
pip install onnx
pip install python-lzf
```

## 3. Install pypcd

```bash
git clone https://github.com/klintan/pypcd.git
cd pypcd
python setup.py install
```

## 4. Install pytorch-quantization

```bash
git clone -b v8.6.1 https://github.com/NVIDIA/TensorRT.git
cd TensorRT/tools/pytorch-quantization
python setup.py install
```
