# Intel Powered AI

Here you will find guidance that covers the frameworks, models, and tools used to build and
optimize robot perception and intelligence workloads.

## AI Toolkits

AI Frameworks are the runtimes and toolkits that train, optimize, deploy, and serve
models on the development kit. Each framework targets OpenVINO, so inference runs across
the Intel CPU, GPU, and NPU and integrates with the ROS 2 and control stack.

::::{grid} 2

:::{grid-item-card} **Gen AI**
:link: gen-ai/index
:link-type: doc
:link-alt: clickable cards

Serve large language models on the robot for natural-language command interpretation, task planning, and reasoning, offline and on-device.
:::

:::{grid-item-card} **Vision AI**
:link: vision-ai/index
:link-type: doc
:link-alt: clickable cards

Train, optimize, and run the perception models that let a robot detect objects, segment scenes, and inspect for defects.
:::

:::{grid-item-card} **Physical AI**
:link: physical-ai/index
:link-type: doc
:link-alt: clickable cards

Develop and run the robot-learning and embodied-AI policies that map perception to action.
:::
::::

## Developer Tools

Use these tools to develop, optimize, and profile AI workloads for Robotics AI
Suite applications. Install versions supported by the relevant application or
Blueprint; do not combine independently pinned toolkit versions without
validating the resulting environment.

| Tool | Use |
| --- | --- |
| [OpenVINO](https://docs.openvino.ai/) | Optimize and deploy deep-learning inference workloads. |
| [Intel oneAPI Toolkits](https://www.intel.com/content/www/us/en/developer/tools/oneapi/overview.html) | Develop and profile heterogeneous C++, SYCL, and data-parallel workloads. |
| [OpenVINO Physical AI Runtime](https://github.com/openvinotoolkit/physicalai) | Accelerate your OpenVINO-powered deployment with a unified API for connecting cameras, robots, and policy inference. |
| [Intel Physical AI Studio](https://github.com/open-edge-platform/physical-ai-studio)| Train and depoy VLA models with an easy-to-use imitation learning dataset generation platform. |

For performance analysis, see [Benchmarking and Profiling](../components/benchmarking/index.md).


::::{grid} 2

:::{grid-item-card} **OpenVINO**
:link: openvino/index
:link-type: doc
:link-alt: clickable cards

Optimize and deploy deep-learning inference on available Intel compute devices.
:::

:::{grid-item-card} **Developer Tools**
:link: developer_tools/index
:link-type: doc
:link-alt: clickable cards

Install and configure OpenVINO, oneAPI, IPEX, IPEX-LLM, and OpenXLA.
:::

:::{grid-item-card} **Agentic Skills**
:link: skills/index
:link-type: doc
:link-alt: clickable cards

Find skills for use with the Robotics AI Suite to power AI-enabled development.
:::
::::
