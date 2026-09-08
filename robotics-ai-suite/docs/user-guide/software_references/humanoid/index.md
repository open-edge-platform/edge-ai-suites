# Humanoid Sample Pipelines

The Humanoid Toolkit sample pipelines demonstrate end-to-end AI workflows optimized for Intel platforms. Review the [validated hardware configuration](../../hardware_blueprints/humanoid/index.md#validated-configuration) before running a pipeline.


::::{grid} 3

:::{grid-item-card} **Sample Pipelines**
:link: sample_pipelines
:link-type: doc
:link-alt: clickable cards

End-to-end reference pipelines demonstrating imitation learning, vision-based manipulation, SLAM, and LLM-guided task execution.
:::

:::{grid-item-card} **Package Reference**
:link: packages_list
:link-type: doc
:link-alt: clickable cards

Find supported Humanoid runtime, middleware, sensor, and pipeline packages.
:::
::::


## Sample Pipelines Overview

| Pipeline | Domain | Description |
|---|---|---|
| **[Imitation Learning - ACT](sample_pipelines/imitation_learning_act.md)** | Manipulation, AI | Action Chunking with Transformers optimized with OpenVINO™ for ALOHA robots. |
| **[Diffusion Policy](sample_pipelines/diffusion_policy.md)** | Manipulation, AI | Visuomotor diffusion policy for the Push-T manipulation task. |
| **[Model Predictive Control Demo](sample_pipelines/mpc_demo.md)** | Manipulation, Control | ACT imitation learning with OCS2 MPC and MuJoCo simulation. |
| **[VSLAM: ORB-SLAM3](sample_pipelines/ORB_VSLAM.md)** | SLAM, Perception | Feature-based visual SLAM for monocular, stereo, and RGB-D cameras. |
| **[Robotics Diffusion Transformer (RDT)](sample_pipelines/robotics_diffusion_transformer.md)** | Foundation Model, AI | Bimanual manipulation foundation model running in MuJoCo and real ALOHA robots. |
| **[Pi0.5 with Real-Time Chunking](sample_pipelines/pi05_with_rtc.md)** | VLA, Manipulation | Vision-Language-Action pipeline with PaliGemma VLM and flow-matching policy. |
| **[LLM Robotics Demo](sample_pipelines/llm_robotics.md)** | GenAI, Manipulation | Voice and text-commanded robot control with Phi-4 and SAM/CLIP. |
| **[OpenClaw AgenticROS Demo](sample_pipelines/openclaw_agenticros_demo.md)** | Agentic AI, ROS 2 | Agentic ROS framework demo with OpenClaw. |
| **[Fast-LIO2 Demo](sample_pipelines/fast_lio2_demo.md)** | LiDAR, SLAM | Fast, robust LiDAR-inertial odometry package. |
| **[Fast-LIVO2 Demo](sample_pipelines/fast_livo2_demo.md)** | LiDAR, Visual SLAM | Fast LiDAR-inertial-visual odometry package. |
| **[Point-LIO Demo](sample_pipelines/point_lio_demo.md)** | LiDAR, SLAM | Robust LiDAR-inertial odometry via point-by-point integration. |
| **[GR00T Whole-Body Control](sample_pipelines/gr00t_wbc.md)** | Control, Manipulation | Whole-body control pipeline for humanoid robotics. |
| **[GR00T N1D7 OpenVINO](sample_pipelines/gr00t_n1d7_ov.md)** | AI Inference | OpenVINO-accelerated GR00T foundation model deployment. |


:::{toctree}
:maxdepth: 2
:hidden:
Humanoid Packages <packages_list>
Sample Pipelines <sample_pipelines>
:::

