# Sample Pipelines

Sample pipelines are provided to demonstrate the capabilities of the Humanoid Toolkit. Review the [validated hardware configuration](../../hardware_blueprints/humanoid/index.md#validated-configuration) before running a pipeline.

These pipelines are designed to showcase core Humanoid Toolkit features, including imitation learning, vision-based manipulation and SLAM. Each pipeline includes a detailed description, along with instructions for running the sample code on your system.



::::{grid} 2

:::{grid-item-card} **Imitation Learning - ACT**
:link: sample_pipelines/imitation_learning_act
:link-type: doc
:link-alt: clickable cards

Train and evaluate an Action Chunking Transformer policy in simulation or on a robot.
:::

:::{grid-item-card} **Model Predictive Control Demo**
:link: sample_pipelines/mpc_demo
:link-type: doc
:link-alt: clickable cards

Combine ACT, OCS2 model predictive control, and MuJoCo simulation.
:::

:::{grid-item-card} **Diffusion Policy**
:link: sample_pipelines/diffusion_policy
:link-type: doc
:link-alt: clickable cards

Evaluate Transformer- and CNN-based diffusion policies on the Push-T task.
:::

:::{grid-item-card} **VSLAM: ORB-SLAM3**
:link: sample_pipelines/ORB_VSLAM
:link-type: doc
:link-alt: clickable cards

Run visual and visual-inertial SLAM with RGB-D, stereo, or monocular cameras.
:::

:::{grid-item-card} **LIO SLAM: Point-LIO**
:link: sample_pipelines/point_lio_demo
:link-type: doc
:link-alt: clickable cards

Build and run point-cloud lidar-inertial odometry and mapping.
:::

:::{grid-item-card} **LLM Robotics Demo**
:link: sample_pipelines/llm_robotics
:link-type: doc
:link-alt: clickable cards

Use large-language-model planning and perception in a robotics workflow.
:::

:::{grid-item-card} **Robotics Diffusion Transformer**
:link: sample_pipelines/robotics_diffusion_transformer
:link-type: doc
:link-alt: clickable cards

Deploy a diffusion-transformer policy for robot manipulation tasks.
:::

:::{grid-item-card} **Pi0.5 with Real-Time Chunking**
:link: sample_pipelines/pi05_with_rtc
:link-type: doc
:link-alt: clickable cards

Run a Pi0.5 vision-language-action model with real-time action chunking.
:::

:::{grid-item-card} **OpenClaw + AgenticROS Deployment**
:link: sample_pipelines/openclaw_agenticros_demo
:link-type: doc
:link-alt: clickable cards

Deploy an OpenClaw agent with AgenticROS and an OpenVINO Model Server.
:::

:::{grid-item-card} **Fast-LIVO2 Demo**
:link: sample_pipelines/fast_livo2_demo
:link-type: doc
:link-alt: clickable cards

Run real-time lidar-inertial-visual odometry and mapping.
:::

:::{grid-item-card} **LIO SLAM: FAST-LIO2**
:link: sample_pipelines/fast_lio2_demo
:link-type: doc
:link-alt: clickable cards

Build and run high-performance lidar-inertial odometry and mapping.
:::

:::{grid-item-card} **GEAR-SONIC Introduction**
:link: sample_pipelines/gr00t_wbc
:link-type: doc
:link-alt: clickable cards

Explore whole-body control for GROOT-based humanoid robotics.
:::

:::{grid-item-card} gr00t-n1.7
:link: sample_pipelines/gr00t_n1d7_ov
:link-type: doc
:link-alt: clickable cards

Optimize and deploy the GR00T N1.7 model with OpenVINO.
:::
::::



:::{toctree}
:hidden:

sample_pipelines/imitation_learning_act
sample_pipelines/mpc_demo
sample_pipelines/diffusion_policy
sample_pipelines/ORB_VSLAM
sample_pipelines/point_lio_demo
sample_pipelines/llm_robotics
sample_pipelines/robotics_diffusion_transformer
sample_pipelines/pi05_with_rtc
sample_pipelines/openclaw_agenticros_demo
sample_pipelines/fast_livo2_demo
sample_pipelines/fast_lio2_demo
sample_pipelines/gr00t_wbc
sample_pipelines/gr00t_n1d7_ov

:::


