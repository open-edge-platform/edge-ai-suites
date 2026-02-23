<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/health-and-life-sciences-ai-suite/multi_modal_patient_monitoring">
     GitHub project
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/health-and-life-sciences-ai-suite/multi_modal_patient_monitoring/README.md">
     Readme
  </a>
</div>
hide_directive-->

# Multi-Modal Patient Monitoring

The Multi-Modal Patient Monitoring application is a reference workload that demonstrates how
multiple AI pipelines can run simultaneously on a single Intel® platform, providing
consolidated monitoring for a virtual patient.

It combines several AI services:

- **rPPG (Remote Photoplethysmography):** Contactless heart and respiratory rate estimation
from facial video.
- **3D-Pose Estimation:** 3D human pose detection from video.
- **AI-ECG:** ECG rhythm classification from simulated ECG waveforms.
- **MDPNP:** Getting metrics of three simulated devices such as ECG, BP and CO2
- **Patient Monitoring Aggregator:** Central service that collects and aggregates vitals from
all AI workloads.
- **Metrics Collector:** Gathers hardware and system telemetry (CPU, GPU, NPU, power) from
the host.
- **UI:** Web-based dashboard for visualizing waveforms, numeric vitals, and system status.

Together, these components illustrate how vision- and signal-based AI workloads can be
orchestrated, monitored, and visualized in a clinical-style scenario.

## Supporting Resources

- [Get Started](./get-started.md) – Step-by-step instructions to build and run the application
using `make` and Docker.
- [System Requirements](./get-started/system-requirements.md) – Hardware, software, and network requirements, plus an overview of the AI models used by each workload.
- [How It Works](./how-it-works.md) – High-level architecture, service responsibilities, and
data/control flows.

> This application is provided for development and evaluation purposes only and is *not* intended for clinical or diagnostic use.

<!--hide_directive
:::{toctree}
:hidden:

get-started.md
how-it-works.md

:::
hide_directive-->