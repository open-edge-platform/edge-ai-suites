# Humanoid Toolkit

Humanoid Toolkit is an intuitive, easy-to-use software stack designed to
streamline the development of humanoid products and applications on Intel
platforms. The toolkit provides a comprehensive environment for developing,
testing, and optimizing humanoid software and algorithms. It includes the
necessary software frameworks, libraries, tools, best-known configurations
(BKC), tutorials, and example code for AI solution development.

Humanoid Toolkit includes the following features:

- Comprehensive software platform from BSP and acceleration libraries
  to reference demos, with documentation and developer tutorials;

- Real-time BKC, Linux real-time kernel and optimized EtherCAT;

- Traditional vision and motion planning acceleration on CPU,
  Reinforcement/Imitation Learning-based manipulation, AI-based vision
  & LLM/VLM acceleration on iGPU & NPU;

- Typical workflows and examples including ACT/DP-based manipulation,
  LLM task planning, Pick & Place, ORB-SLAM3, etc.

## Software Architecture

The following diagram shows the high-level Humanoid Toolkit software
architecture:

:::{image} assets/images/sdk_architecture.png
:align: center
:::

This software architecture is designed to power Humanoid Toolkit
systems by integrating computer vision, AI-driven manipulation,
locomotion, SLAM, and large models into a unified framework. Built on
ROS2 middleware, it takes advantage of Intel's CPU, iGPU, dGPU, and NPU
to optimize performance for robotics and AI applications. The stack
includes high-performance AI frameworks, real-time libraries, and
system-level optimizations, making it a comprehensive solution for
humanoid products.

At the highest level, the architecture is structured around key
reference pipelines and demos that demonstrate its core capabilities.
These include Vision Servo, which enhances robotic perception using
AI-powered vision modules, and ACT-based Manipulation, which applies
reinforcement learning and imitation learning to improve robotic
grasping and movement. Optimized Locomotion leverages traditional
control algorithms like MPC (Model Predictive Control) and LQR (Linear
Quadratic Regulator), alongside reinforcement learning models for
adaptive motion. Additionally, the ORB-SLAM3 pipeline focuses on
real-time simultaneous localization and mapping, while LLM Task Planning
integrates large language models for intelligent task execution.

Beneath these pipelines, the software stack includes specialized AI and
robotics modules. The vision module supports CNN-based models, OpenCV,
and PCL operators for optimized perception, enabling robots to interpret
their surroundings efficiently. The manipulation module combines
traditional motion planning with AI-driven control, allowing robots to
execute complex movements. For locomotion, the system blends classic
control techniques with reinforcement learning models, ensuring smooth
and adaptive movement. Meanwhile, SLAM components such as GPU ORB
extraction and ADBSCAN optimization enhance mapping accuracy, and BEV
(Bird's Eye View) models contribute to improved spatial awareness. The
large model module supports LLMs, Vision-Language Models (VLM), and
Vision-Language-Action Models (VLA), enabling advanced reasoning and
decision-making capabilities.

At the core of the system is ROS2 middleware and acceleration
frameworks, which provide a standardized framework for robotics
development. The architecture is further enhanced by Intel's AI
acceleration libraries, including OpenVINO™ for deep learning inference,
Intel® LLM Library for PyTorch (IPEX-LLM) for optimized large model
execution, and compatibility with TensorFlow*, PyTorch*, and ONNX*. The
Intel® oneAPI DPC++/C++ Compiler and libraries offer
high-performance computing capabilities, leveraging oneMKL for
mathematical operations, oneDNN for deep learning, and oneTBB for
parallel processing. Additionally, Intel's real-time libraries ensure
low-latency execution, with tools for performance tuning and
EtherCAT-based industrial communication.

To ensure seamless integration with robotic hardware, the toolkit runs on a
real-time optimized Linux board support package. It includes support for
optimized EtherCAT and camera drivers, along with Intel-specific
features such as Speed Shift Technology and Cache Allocation to enhance
power efficiency and performance. These system-level enhancements allow
the software stack to deliver high responsiveness, making it suitable
for real-time robotics applications.

Overall, the Humanoid Toolkit provides a highly optimized, AI-driven framework
for robotics and humanoid applications, combining
computer vision, motion planning, real-time processing, and large-scale
AI models into a cohesive system. By leveraging Intel's hardware
acceleration and software ecosystem, it enables next-generation robotic
applications with enhanced intelligence, efficiency, and adaptability.

## Validated Configuration

The Humanoid Blueprint supports the validated configuration below. It defines
the hardware and software baseline for the Humanoid Toolkit; use it when
preparing a system for Humanoid workflows.

### Intel Core Ultra Series 2

| Component | Validated configuration |
| --- | --- |
| Processor | Intel Core Ultra 7 255H processor; 2.0 GHz base frequency, 5.1 GHz maximum turbo frequency, and 28 W base power |
| Memory | 64 GB dual-channel LPDDR5X memory, 7467 MT/s |
| Discrete GPU | Intel Arc B580 discrete GPU with 12 GB GDDR6 memory; 2.3 GHz base frequency, MXM 3.1 Type B PCIe Gen4 x8 interface, and 150 W TDP |
| Operating system | Canonical Ubuntu 22.04 LTS (Jammy Jellyfish), 64-bit Desktop |
| ROS 2 | Humble Hawksbill |
| Kernel | Intel ECI 6.12.8 real-time kernel with PREEMPT_RT support |

This configuration supports real-time motion-control, computer-vision,
imitation-learning, and large-model workflows. Individual pipelines can require
additional model, sensor, firmware, or package setup.

- [Real-Time Linux](../../components/realtime_determinism/realtime_linux.md) configures the kernel
  and runtime tuning.
- [Packages List](../../software_references/humanoid/packages_list.md) lists the
  supported motion-control, sensor, and pipeline packages.

### Not Yet Validated

PTL 358H with Ubuntu 24.04, ROS 2 Jazzy, and the 6.17.11 real-time kernel is
not currently validated for this Blueprint. Do not apply that platform baseline
to Humanoid workflows until it is documented here as a validated configuration.


