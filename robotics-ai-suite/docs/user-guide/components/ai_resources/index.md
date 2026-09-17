# AI Resources

Here you will find guidance that covers the frameworks, models, and tools used to build and
optimize robot perception and intelligence workloads.

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

For performance analysis, see [Benchmarking and Profiling](../benchmarking/index.md).

<!--hide_directive
::::{grid} 2hide_directive-->

<!--hide_directive:::{grid-item-card}hide_directive--> **OpenVINO**
<!--hide_directive:link: openvino/index
:link-type: doc
:link-alt: clickable cardshide_directive-->

Optimize and deploy deep-learning inference on available Intel compute devices.
<!--hide_directive:::hide_directive-->

<!--hide_directive:::{grid-item-card}hide_directive--> **Developer Tools**
<!--hide_directive:link: developer_tools/index
:link-type: doc
:link-alt: clickable cardshide_directive-->

Install and configure OpenVINO, oneAPI, IPEX, IPEX-LLM, and OpenXLA.
<!--hide_directive:::hide_directive-->

<!--hide_directive:::{grid-item-card}hide_directive--> **Agentic Skills**
<!--hide_directive:link: skills/index
:link-type: doc
:link-alt: clickable cardshide_directive-->

Find skills for use with the Robotics AI Suite to power AI-enabled development.
<!--hide_directive:::
::::
hide_directive-->

<!--hide_directive
:::{toctree}
:maxdepth: 1
:hidden:

OpenVINO <openvino/index>
Developer Tools <developer_tools/index>
Agentic Skills <skills/index>
:::
hide_directive-->