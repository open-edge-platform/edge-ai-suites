# Initial Application: Multi-Modal Patient Monitoring

The Multi-Modal Patient Monitoring application helps medical AI developers and systems engineers at medical OEMs/ODMs (GE Healthcare, Philips, Mindray) evaluate Intel® Core™ Ultra processors for AI‑enabled patient monitoring. It demonstrates that you can run **multiple AI workloads concurrently on a single Intel‑powered edge device** without a discrete GPU.

You can view four key patient monitoring workloads side‑by‑side through a GUI dashboard. Each workload displays:

- MDPnP OpenICE device integration (vital signs and device data)
- 3D pose estimation (OpenVINO webcam demo)
- AI‑ECG analysis
- Remote PPG (rPPG) for contactless vital sign estimation

Outputs from these workloads are consolidated into a 2×2 layout, showing each stream in its own quadrant while sharing a single Intel Core Ultra CPU + iGPU + NPU platform. This helps validate BOM reduction and deployment simplification by consolidating multi‑modal AI on one edge system.

The solution is intended to:

- Showcase multi‑modal AI capabilities of Intel Core Ultra
- Run on Ubuntu 24.04 with containerized workloads
- Be startable with a **single command** from a clean system (end‑to‑end setup and launch targeted in ≤ 30 minutes)

Secure provisioning (for example, Polaris Peak integration) is not part of the initial implementation, but the architecture is intended to be extensible for future security integrations.

## Get Started

To see the system requirements and other installations, see the following guides:

- [Get Started](./docs/user-guide/get-started.md): Follow step-by-step instructions to set up the application.
- [System Requirements](./docs/user-guide/get-started/system-requirements.md): Check the hardware and software requirements for deploying the application.
- [Run the application](./docs/user-guide/run-multi-modal-app.md): Run Multi-Modal Patient Monitoring application.

## How It Works

At a high level, the system is composed of several microservices that work together to ingest patient signals and video, run AI models on Intel hardware (CPU, GPU, and NPU), aggregate results, and expose them to a UI for clinicians.

![System design](./docs/user-guide/_assets/system-design.png)

## Learn More

For detailed information about system requirements, architecture, and how the application works, see the

- [Full Documentation](./docs/user-guide/index.md)
