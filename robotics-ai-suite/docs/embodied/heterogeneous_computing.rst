Heterogeneous Computing
########################

In modern Embodied Intelligence applications, a variety of software workloads are integrated to enable autonomous systems to perform complex tasks in dynamic environments. These workloads span across different domains, each with its specific computational and algorithmic requirements. 

Here's a more detailed breakdown:

**Real-time Motion Control**: 

- Real-time motion control involves algorithms responsible for the precise control of actuators to achieve desired movements. This includes low-level control tasks like position, velocity, and force regulation using techniques such as PID (Proportional-Integral-Derivative) controllers, model-based control (e.g., Kalman filters), and adaptive control strategies. These systems must operate with low latency to ensure smooth interaction with the environment, requiring high-performance computational pipelines and sometimes specialized hardware accelerators.

**Locomotion** based on Model Predictive Control (MPC) or Reinforcement Learning (RL): 

- MPC uses a model of the robot's dynamics and optimizes control actions over a finite horizon, predicting future states to minimize a cost function while respecting system constraints. This is computationally intensive due to the need for solving optimization problems at every timestep. RL-based Locomotion leverages policies learned through trial-and-error, with agents exploring and exploiting their environment to optimize walking, running, or other locomotion tasks. These approaches often require significant training time and computational resources for fine-tuning.

**Manipulation** based on Traditional Motion Planning or Imitation Learning: 

- Traditional Motion Planning involves various algorithms to plan feasible paths for manipulation tasks, avoiding obstacles while considering kinematic constraints. These methods are well-suited for scenarios with relatively predictable environments but can be computationally expensive for high-dimensional systems. Imitation Learning (IL) uses expert demonstrations to teach the robot how to perform tasks like grasping, object manipulation, and tool usage. By leveraging supervised learning or inverse reinforcement learning (IRL), the robot learns to replicate human-like actions and behaviors. 

**Vision Algorithms**: 

- OpenCV-based Vision Algorithm is commonly used for classical computer vision tasks such as feature extraction, object detection, motion tracking, and image stitching. These algorithms rely on techniques such as edge detection (e.g., Canny), optical flow, and stereo vision, and are computationally efficient but less robust in complex, dynamic environments. CNN models are extensively used for image classification, object detection, and semantic segmentation in robotic vision tasks. These models are typically pre-trained on large datasets like ImageNet and fine-tuned for task-specific objectives. Advanced architectures like ResNet, EfficientNet, or Mask R-CNN can be deployed for real-time perception tasks. More recent innovations, such as Vision Transformers (ViTs), apply transformer-based architectures to vision tasks. These models excel at handling long-range dependencies and can outperform traditional CNN-based models in certain scenarios. Vision transformers are becoming a key technology in large-scale vision systems due to their ability to model complex relationships in large image datasets.

**Visual SLAM** (Simultaneous Localization and Mapping): 

- It integrates visual input from cameras with sensor data (e.g., IMUs, LiDAR) to enable robots to build a map of their environment while simultaneously localizing themselves within it. Techniques such as ORB-SLAM  are used to process visual features and track the robot's position in real-time. SLAM requires fast feature extraction and matching, robust loop closure detection, and optimization techniques (e.g., bundle adjustment) to ensure accurate and consistent localization.

**Large Language Models (LLMs)** or **Vision-Language Models (VLMs)**:

- LLMs like GPT (Generative Pretrained Transformer) or BERT (Bidirectional Encoder Representations from Transformers) are used to enable natural language understanding and generation. These models can be integrated with Embodied Intelligence systems to facilitate tasks such as dialogue-based control, instruction understanding, and decision-making processes. Vision-Language Models integrate vision and language by using multi-modal representations, where models such as CLIP (Contrastive Language-Image Pretraining) or Flamingo align visual and textual inputs. These models enable robots to understand instructions given in natural language and respond appropriately with visual understanding. Tasks like image captioning, visual question answering (VQA), and referring expression comprehension (RE) are possible with these multi-modal models.

End-to-End **Vision-Action Imitation Learning Models**: 

- These models directly map raw sensory inputs (such as images or videos) to actions (e.g., movements or manipulations) using Transformer architecture. They are used for tasks like vision-based grasping or navigation. In such models, the robot learns to perform complex tasks directly from raw sensory data by training end-to-end on large datasets, allowing it to generalize across different environments and conditions. These models combine perception, planning, and control into a unified framework.

Each of these workloads represents a unique challenge and requires specialized algorithms, architectures, and computational resources. Embodied Intelligence systems rely on an integration of these components to function effectively in real-world environments, requiring high performance and scalability for real-time decision-making, robust interaction with the environment, and adaptation to dynamic scenarios.

Heterogeneous Computing of Embodied Intelligence development kit
===================================================================
The Intel Core Ultra 7 255H processor, part of Intel's Core Ultra processor series 2, is engineered to deliver high performance and efficiency for mobile computing platforms. Building upon previous information, here's a more detailed exploration of its features and capabilities:

* Advanced Hybrid **CPU** Architecture: the Core Ultra 7 255H utilizes a sophisticated hybrid architecture, combining different core types to optimize performance across various workloads.

  .. admonition:: CPU Architecture 

    | **Performance Cores (P-cores):** 6 Lion Cove cores, each capable of reaching up to 5.1 GHz. These cores are tailored for tasks demanding high single-threaded performance.
    | **Efficient Cores (E-cores):** 8 Skymont cores, with a maximum frequency of 4.4 GHz, designed for multi-threaded tasks and energy efficiency.
    | **Low Power Efficient Cores (LP E-cores):** 2 additional Skymont cores, operating up to 2.5 GHz, dedicated to handling low-power background tasks.

  With this advanced hybrid CPU architecture, 255H achieved significant performance improvement on single-threaded computing and multi-threaded computing over its predecessor, the Core Ultra 7 155H, with PassMark test.  

* **Integrated GPU (iGPU)**

  The Intel Arc 140T iGPU in the Core Ultra 7 255H is designed to deliver high computational throughput with a combination of Xe-cores and XMX (Xe Matrix Extensions) arrays for AI workloads. This ensures high parallel processing performance for graphics rendering, AI inferencing, and general-purpose GPU acceleration. The XMX arrays within the iGPU provide dedicated AI acceleration, reaching up to 72 TOPS in INT8 operations. New Xe-LPG+ Architecture of Arrow Lake H iGPU is an evolution of Intel's Xe-LPG graphics, bringing power-efficient performance with improved shading and AI capabilities, Optimized for power efficient on AI and Graphics Tasks.

* **NPU**

  The Intel Core Ultra 7 255H processor incorporates a dedicated Neural Processing Unit (NPU), branded as Intel® AI Boost, designed to efficiently handle complex AI workloads with enhanced performance and energy efficiency. This NPU delivers up to 11 TOPS (Tera Operations Per Second) for INT8 operations, enabling rapid processing of AI tasks such as image recognition and natural language processing. Operating at approximately 2 watts, the NPU offers a significant improvement in AI performance per watt compared to traditional CPU processing, making it ideal for sustained AI workloads. The NPU is also optimized for deployment via Intel's OpenVINO™ toolkit, facilitating seamless integration and acceleration of AI applications across various Intel hardware components. 

* **Intel Arc B580 discrete GPU**

  Intel Arc B580 (code name Battlemage) represents Intel's strategic push into AI-accelerated computing, combining gaming prowess with AI-specific hardware. Its Xe2 architecture, XMX units, and high bandwidth graphics memory make it a compelling choice for gamers, creators, and developers seeking affordable yet powerful AI capabilities. Intel's XeSS technology uses AI to upscale lower-resolution images to higher resolutions while maintaining visual fidelity. This reduces GPU load and improves frame rates. The GPU's 12GB VRAM and high memory bandwidth (418 GB/s) enable efficient handling of large AI models and datasets, making it viable for machine learning tasks such as model training and inference in local environments. Support for OpenVINO and other AI frameworks ensures compatibility with popular developer tools, facilitating seamless integration into various pipelines of Embodied Intelligence.

In summary, the Intel Embodied Intelligence development kit offers a versatile and powerful solution for heterogeneous computing, combining advanced core architecture, robust integrated graphics, neuron processing unit and discrete GPU to provide enhanced AI capabilities, and efficient power management to meet the demands of Embodied Intelligence use cases.

Allocate Embodied Intelligence workloads onto different compute device
========================================================================
Based on the nature of different Embodied Intelligence workloads, we can allocate them to CPU, iGPU, NPU and dGPU, to take full advantage of Embodied Intelligence development kit's heterogeneous computing capability and improve efficiency of executing those workloads.

+-------------------------+--------------+---------------------------------------------------------------------+
|Workloads                |Compute Device|Rationale                                                            |
+-------------------------+--------------+---------------------------------------------------------------------+
|Real-time Motion Control |CPU           |Motion control algorithms that require low-latency and deterministic |
|                         |              |processing (such as PID control, sensor fusion, and real-time        |
|                         |              |feedback loops). These systems must operate with low latency to      |
|                         |              |ensure smooth interaction with the environment, requiring            |
|                         |              |high-performance computational pipelines.                            |
+-------------------------+--------------+---------------------------------------------------------------------+
|MPC / RL-based Locomotion|CPU / iGPU    |iGPU should be used to accelerate the inference of trained models, as|
|                         |              |it is optimized for high-throughput tensor computations, such as     |
|                         |              |those involved in RL algorithms and trajectory planning. CPU can     |
|                         |              |manage the overall orchestration of the motion planning process,     |
|                         |              |including model management, decision-making loops, and environment   |
|                         |              |interaction. Additionally, the CPU will handle non-parallelizable    |
|                         |              |logic, task sequencing, and lower-level computations.                |
+-------------------------+--------------+---------------------------------------------------------------------+
|Manipulation based on    |CPU           |Traditional motion planning algorithms are typically control-        |
|Traditional Motion       |              |intensive and may involve heuristic-based decisions with frequent    |
|Planning                 |              |environment re-planning. The CPU is ideal for handling pathfinding,  |
|                         |              |planning logic, and decision-making for manipulation tasks.          |
+-------------------------+--------------+---------------------------------------------------------------------+
|Manipulation based on    |CPU / iGPU    |iGPU can accelerate the inference of learned models that map sensory |
|Imitation Learning       |              |inputs (images or sensor data) to actions. It can also efficiently   |
|                         |              |handle neural network inferences is crucial when translating         |
|                         |              |demonstration data into policies for manipulation tasks.             |
+-------------------------+--------------+---------------------------------------------------------------------+
|Visual SLAM              |CPU / iGPU /  |CPU should handle the overall SLAM system coordination, including    |
|                         |NPU           |managing the visual map, sensor fusion, and real-time optimization   |
|                         |              |(e.g., bundle adjustment, loop closure detection), which often       |
|                         |              |involves complex iterative algorithms that benefit from the CPU's    |
|                         |              |serial processing capabilities. iGPU can accelerate visual SLAM      |
|                         |              |components, particularly those related to image feature extraction,  |
|                         |              |stereo matching, and dense visual odometry. GPUs excel in processing |
|                         |              |large amounts of visual data in parallel, making them suitable for   |
|                         |              |real-time visual feature extraction. If the SLAM system integrates   |
|                         |              |deep learning for feature matching or object recognition (e.g., using|
|                         |              |neural networks for loop closure detection or semantic segmentation),|
|                         |              |the NPU should be used for accelerating the AI inference tasks.      |
+-------------------------+--------------+---------------------------------------------------------------------+
|Vision Algorithms        |NPU / iGPU    |NPU and iGPU should be utilized for general-purpose vision tasks,    |
|(OpenCV, CNN based       |              |such as running OpenCV algorithms (e.g., feature extraction, motion  |
|models)                  |              |tracking, stereo vision) and lightweight CNN-based models for        |
|                         |              |real-time image processing tasks. These tasks are typically less     |
|                         |              |compute-intensive compared to large-scale vision models and can      |
|                         |              |benefit from parallel execution on iGPU.                             |
+-------------------------+--------------+---------------------------------------------------------------------+
|Vision Algorithms        |iGPU / dGPU   |For more computationally intensive tasks of transformer-based vision |
|(Transformer based       |              |models (e.g., Vision Transformers or CLIP), the iGPU / dGPU should be|
|models)                  |              |leveraged. These models require more computational resources,        |
|                         |              |especially when processing high-resolution video or large image      |
|                         |              |datasets, making the iGPU / dGPU a perfect fit for these workloads.  |
+-------------------------+--------------+---------------------------------------------------------------------+
|LLM / VLM                |iGPU / dGPU   |These models involve large-scale transformer networks that require   |
|                         |              |substantial GPU resources to run efficiently, especially for         |
|                         |              |inference tasks with high throughput requirements. The discrete GPU  |
|                         |              |can handle the parallel processing of the massive matrix             |
|                         |              |multiplications and transformer layers involved. Depending on        |
|                         |              |parameter size of LLM / VLM, iGPU / dGPU can be leveraged.           |
+-------------------------+--------------+---------------------------------------------------------------------+
|end to end VA models     |dGPU / edge   |These models typically require significant GPU compute power,        |
|                         |server        |especially when processing high-resolution video input and performing|
|                         |              |complex actions in response. The discrete GPU accelerates both the   |
|                         |              |perception (vision) and action (control) parts of the model, enabling|
|                         |              |efficient real-time decision-making.                                 |
+-------------------------+--------------+---------------------------------------------------------------------+
