.. _Target_System:

System Requirement
=================================

This section outlines the system requirements for the Embodied Intelligence SDK, detailing the necessary hardware and software components to ensure functionality, compatibility and optimal performance.

**Hardware Requirements**

+-------------------------------+---------------------------------------------------------------+
| **Component**                 | **Specifications**                                            |
+===============================+===============================================================+
| **Processor (CPU)**           | The embodied SDK is powered by the **Arrow Lake 255H          |
|                               | Processor**, a high-efficiency CPU designed for edge          |
|                               | computing and AI-driven applications:                         |
|                               |                                                               |
|                               | - Base Frequency: 2.0 GHz                                     |
|                               | - Max Turbo Frequency: 5.1 GHz                                |
|                               | - Base Power Consumption: 28W                                 |
+-------------------------------+---------------------------------------------------------------+
| **Memory (RAM)**              | To ensure smooth multitasking and data processing, the        |
|                               | Embodied Intelligence SDK prefers **64GB of LPDDR5X**         |
|                               | memory:                                                       |
|                               |                                                               |
|                               | - Memory Type: Dual-channel LPDDR5X                           |
|                               | - Speed: 2R 7467 MT/s                                         |
+-------------------------------+---------------------------------------------------------------+
| **Discrete Graphics Processing| To enable more complex AI workloads, including large          |
| Unit (dGPU)**                 | languages models, vision-action models, the Embodied          |
|                               | Intelligence SDK requires **Battlemage B580 dGPU**, a         |
|                               | dedicated high-performance graphics card engineered for AI    |
|                               | acceleration, real-time graphics rendering, and               |
|                               | computationally intensive tasks:                              |
|                               |                                                               |
|                               | - Memory: 12GB GDDR6 VRAM                                     |
|                               | - Base Frequency: 2.3 GHz                                     |
|                               | - Interface: MXM 3.1 Type B slot with PCIe Gen4 x8            |
|                               | - Thermal Design Power (TDP): 150W                            |
+-------------------------------+---------------------------------------------------------------+

**Software Requirements**

+-------------------------------+---------------------------------------------------------------+
| **Component**                 | **Specifications**                                            |
+===============================+===============================================================+
| **Operating System**          | The Embodied Intelligence SDK runs on **Ubuntu distribution   |
|                               | of the |Linux| OS  version 22.04 LTS**, a long-term support   |
|                               | (LTS) version  optimized for stability, security, and         |
|                               | performance in industrial and AI-driven applications.         |
+-------------------------------+---------------------------------------------------------------+
| **Kernel**                    | The Embodied Intelligence SDK requires **kernel version       |
|                               | 6.12.8 with Real-Time Kernel (RT)** capability for optimized  |
|                               | performance in time-sensitive applications.                   |
+-------------------------------+---------------------------------------------------------------+

