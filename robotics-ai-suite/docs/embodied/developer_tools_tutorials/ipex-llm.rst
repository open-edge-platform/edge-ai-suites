|IPEX-LLM|
###########

|IPEX-LLM| (IPEX-LLM) is an LLM optimization library which accelerates local LLM inference and fine-tuning (LLaMA, Mistral, ChatGLM, Qwen, DeepSeek, Mixtral, Gemma, Phi, MiniCPM, Qwen-VL, MiniCPM-V, etc.) on Intel XPU (CPU, iGPU, NPU, dGPU).

`Model List <https://github.com/intel/ipex-llm/tree/main?tab=readme-ov-file#verified-models>`_ shows the optimized/verified models on IPEX-LLM with state-of-art LLM optimizations, XPU acceleration and low-bit (FP8/FP6/FP4/INT4) support.
Also, IPEX-LLM provides seamless integration with llama.cpp, Ollama, HuggingFace transformers, LangChain, LlamaIndex, vLLM, Text-Generation-WebUI, DeepSpeed-AutoTP, FastChat, Axolotl, HuggingFace PEFT, HuggingFace TRL, AutoGen, ModeScope, etc.

.. list-table::
   :widths: 50 50
   :header-rows: 0

   * - .. image:: assets/images/ipex-llm1.jpg
         :width: 100%
         :align: center
     - .. image:: assets/images/ipex-llm2.jpg
         :width: 100%
         :align: center

For robotics software developers, IPEX-LLM offers the opportunity to empower the development of new applications that combine robotics with LLMs, helping LLMs achieve better performance on Intel platforms.

| Please see more details on github repository: https://github.com/intel/ipex-llm/.

| Before installing |IPEX-LLM|, please make sure you have complete the environment setup in :doc:`../installation_setup` and have |oneAPI| installed.
| Then install |IPEX-LLM| in your python environment by running the following command:

.. code-block:: bash

   $ pip install --pre --upgrade ipex-llm[xpu]==2.2.0b2 --extra-index-url https://pytorch-extension.intel.com/release-whl/stable/xpu/cn/
