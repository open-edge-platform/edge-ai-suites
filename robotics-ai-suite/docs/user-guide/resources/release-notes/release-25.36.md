# Release Notes: Robotics AI Suite 25.36

## Humanoid Toolkit 25.36

Humanoid Toolkit v25.36 enhances model optimization capabilities with OpenVINO™ toolkit and provides typical workflows and examples, including Diffusion Policy (DP), Robotic Diffusion Transformer (RDT), Improved 3D Diffusion Policy (IDP3), Visual Servoing (CNS) and LLM Robotic Demo. This release has also updated the real-time optimized best-known configuration (BKC) on improving AI and control performance, and supporting the Intel® Arc™ B-series graphics card (B570).

**New**

- Updated real-time optimization BKC, including BIOS and runtime optimization, balancing performance with AI and control consolidation.
- Added support for Intel® Arc™ B-series (Battlemage) graphics card (B570).
- Fixed deadlock issue when reading i915 perf event in Preempt-RT kernel.
- New EtherCAT Master stack features supporting user-space EtherCAT Master and multiple EtherCAT masters.
- Added Diffusion Policy pipeline with OpenVINO™ toolkit optimization.
- Added Robotics Diffusion Transformer (RDT) pipeline with OpenVINO toolkit optimization.
- Added Improved 3D Diffusion Policy (IDP3) model with OpenVINO toolkit optimization.
- Added Visual Servoing (CNS) model with OpenVINO toolkit optimization.
- Provided new tutorials for typical AI model optimization with OpenVINO toolkit.
- ACRN hypervisor's initial enablement on Arrow Lake platform.
- Added new Dockerfile to build containerized Robotics Development Toolkit (RDT) pipeline.
- Added pipelines:

  | Pipeline Name                                                               |   Description                                                                                                                                                     |
  |-----------------------------------------------------------------------------|  -----------------------------------------------------------------------------------------------------------------------------------------------------------------|
  | Diffusion Policy ****diffusion_policy****                                   | An innovative method for generating robot actions by conceptualizing visuomotor policy   learning as a conditional denoising diffusion process                    |
  | Robotics Diffusion Transformer (RDT) ****robotics_diffusion_transformer**** | A RDT pipeline provided for evaluating the VLA model on the simulation   task                                                                                     |
  | LLM Robotics Demo ****llm_robotics_demo****                                 | A code generation demo for robotics, interacting with a chatbot utilizing AI   technologies such as large language models (Phi-4) and computer vision (SAM, CLIP) |


**Improved**

The following model algorithms were added and optimized by OpenVINO™ toolkit:

| Algorithm                                                | Description                                                                                                                                                   |
|----------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Qwen2.5VL                                                | Qwen2.5VL ****model_tutorials****                                                                                                                             |
| Whisper                                                  | Whisper ****model_tutorials****                                                                                                                               |
| FunASR (Automatic speech recognition)                    | Refer to the FunASR Setup ****funasr-setup**** in LLM Robotics sample pipeline                                                                                |
| Visual Servoing - CNS ****model_cns****                  | A graph neural network-based solution for image servo utilizing explicit keypoints correspondence obtained from any detector-based feature matching methods   |
| Diffusion Policy ****model_dp****                        | A visuomotor policy learning model in the field of robotic visuomotor policy learning, which represents policies as conditional denoising diffusion processes |
| Improved 3D Diffusion Policy (iDP3) ****model_idp3****   | A diffusion policy model enhancing capabilities for 3D robotic manipulation tasks                                                                             |
| Robotic Diffusion Transformer (RDT-1B) ****model_rdt**** | A diffusion-based foundation model for robotic manipulation                                                                                                   |

**Known Issues**

- ACRN hypervisor feature and performance

  - iGPU performance degradation observed when using passthrough iGPU to VM on ACRN hypervisor.
  - Display becomes unresponsive in VMs when running concurrent AI workloads with iGPU SR-IOV enabled on ACRN hypervisor.
