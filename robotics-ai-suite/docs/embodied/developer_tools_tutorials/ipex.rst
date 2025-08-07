|IPEX|
#######

|IPEX| extends the |PyTorch| library with the latest performance optimizations for Intel's hardware. Optimizations take advantage of Intel® Advanced Vector Extensions 512 (Intel® AVX-512) Vector Neural Network Instructions (VNNI) and Intel® Advanced Matrix Extensions (Intel® AMX) on Intel CPUs as well as Intel XeMatrix Extensions (XMX) AI engines on Intel discrete GPUs. Moreover, |IPEX| provides easy GPU acceleration for Intel discrete GPUs through the |PyTorch| xpu device.

The extension can be loaded as a Python module for Python programs or linked as a C++ library for C++ programs. In Python scripts users can enable it dynamically by importing ``intel_extension_for_pytorch``.

.. image:: assets/images/intel_extension_for_pytorch_structure.png
   :width: 85%
   :align: center

|IPEX| allows developers run their applications on Intel® XPU and get optimized performance without excessive changes from |PyTorch| code, which shortens development and validation cycles.

| Please see more details on `intel-extension-for-pytorch Documentation Website <https://intel.github.io/intel-extension-for-pytorch/>`_ and github repository https://github.com/intel/intel-extension-for-pytorch/.
| Install |IPEX| in your python environment by running the following command:

.. code-block:: bash

   $ python -m pip install torch==2.3.1+cxx11.abi torchvision==0.18.1+cxx11.abi torchaudio==2.3.1+cxx11.abi intel-extension-for-pytorch==2.3.110+xpu oneccl_bind_pt==2.3.100+xpu --extra-index-url https://pytorch-extension.intel.com/release-whl/stable/xpu/us/