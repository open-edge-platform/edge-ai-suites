## Initial Application: Multi-Modal Patient Monitoring

The Multi-Modal Patient Monitoring application is designed for medical AI
developers and systems engineers at medical OEMs/ODMs (for example, GE
Healthcare, Philips, Mindray) who are evaluating Intel Core Ultra
platforms for AI‑enabled patient monitoring. It demonstrates that
multiple AI workloads can run **concurrently on a single Intel‑powered
edge device** without a discrete GPU.

The application provides a GUI‑based experience that runs and visualizes
four key patient monitoring workloads side‑by‑side:

- MDPnP OpenICE device integration (vital signs and device data)
- 3D pose estimation (OpenVINO webcam demo)
- AI‑ECG analysis
- Remote PPG (rPPG) for contactless vital sign estimation

Outputs from these workloads are consolidated into a 2×2 layout, showing
each stream in its own quadrant while sharing a single Intel Core Ultra
CPU + iGPU + NPU platform. This helps validate BOM reduction and
deployment simplification by consolidating multi‑modal AI on one edge
system.

The solution is intended to:

- Showcase multi‑modal AI capabilities of Intel Core Ultra
- Run on Ubuntu 24.04 with containerized workloads
- Be startable with a **single command** from a clean system
	(end‑to‑end setup and launch targeted in ≤ 30 minutes)

Secure provisioning (for example, Polaris Peak integration) is not part
of the initial implementation, but the architecture is intended to be
extensible for future security integrations.

---


## 🐳 Run Multi-Modal Patient Monitoring app Using Pre-Built Images

```
make run
```
---
## 🚀 Run Multi-Modal Patient Monitoring app (Local Build)
```
# Initialize MDPnP submodules and dependencies

make init-mdpnp

# Run the full Health-AI-Suite using locally built images
# Set REGISTRY=false to avoid pulling images from a remote registry

make run REGISTRY=false

```
---
## 🛑 Stop and Clean Up
```
# Stop and clean up all running containers

make down
```
---
## 📘 Documentation
For detailed information about system requirements, architecture, and how the application works, see the 

👉  [Full Documentation](docs/user-guide/index.md)

---