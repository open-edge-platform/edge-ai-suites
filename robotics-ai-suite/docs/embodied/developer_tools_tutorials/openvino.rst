|OpenVINO|
###########

|OpenVINO| is an open-source toolkit for optimizing and deploying deep learning models from cloud to edge. 

It accelerates deep learning inference across various use cases, such as generative AI, video, audio, and language with models from popular frameworks, for example the |PyTorch|, TensorFlow, and ONNX frameworks, to get a better performance across Intel® CPU, GPU, iGPU, NPU and other hardware platforms or accelerators.

.. image:: assets/images/openvino-overview-diagram.jpg
   :width: 85%
   :align: center

For robotics software developers, the |OpenVINO| toolkit provides essential tools and pre-built components to simplify the development of AI inference, computer vision, automatic speech recognition, natural language processing, and other robotics-related functionalities. For example, the Model Zoo component in |OpenVINO| offers optimized pre-trained models, allowing developers to quickly get started.At the same time, the |OpenVINO| toolkit can quickly port models to different Intel platforms based on various needs, adapting to complex deployment environments. It addresses the component installation issues associated with deploying algorithms and models on heterogeneous endpoints, effectively enhancing terminal performance.

.. _openvino_install:

| Please see more details on `OpenVINO Toolkit Overview Website <https://www.intel.com/content/www/us/en/developer/tools/openvino-toolkit/overview.html>`_.
| Simply install OpenVINO in your python environment by running the following command:

.. code-block:: bash

   $ pip install openvino==2025.0

