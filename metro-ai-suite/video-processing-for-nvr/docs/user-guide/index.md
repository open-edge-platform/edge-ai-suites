# Video Processing for NVR

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/release-2026.1.0/metro-ai-suite/video-processing-for-nvr">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.1.0/metro-ai-suite/video-processing-for-nvr/README.md">
     Readme
  </a>
</div>
hide_directive-->

Video Processing for NVR is a set of reference applications, built on the **Video Processing
Platform SDK**, that lets developers evaluate and optimize video-processing
workflows for Network Video Recorder (NVR) and similar video-centric products on Intel
platforms.

The Video Processing Platform SDK provides an ARM ecosystem-friendly video-processing acceleration API for
implementing video-centric workloads — such as Network Video Recorder (NVR), Video Conference
Terminal, and Video Matrix — on the Linux platform. It offloads compute-intensive media tasks
(decode, encode, post-processing, composition, and display) to Intel integrated and discrete
GPUs.

This sample application uses the Video Processing Platform SDK as a reference for various video-processing use
cases:

- **Reference sample applications** — located in the `example` folder, these are built with
  the Video Processing Platform SDK APIs to construct Video Analytic and Transcoding workflows (for example, decode +
  post-processing + YOLO/ResNet inference, and decode + post-processing + encode).
- **Smart Video Evaluation Tool 2 (SVET2)** (legacy solution) — a configuration-driven reference application for
  the NVR scenario. For the detailed workflow and configuration reference, see the [SVET2 Guide](https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.1.0/metro-ai-suite/video-processing-for-nvr/docs/user-guide/svet-guide.md).

- **Programming Language:** C/C++

## How It Works

Video Processing for NVR builds on the Video Processing Platform SDK and the media capabilities of Intel GPUs. For
the platform overview, SDK architecture, module and pipeline model, and the `svet_app`
architecture, see [How It Works](./how-it-works.md).

## Learn More

- [Get Started](./get-started.md): Build and run the Video Analytic and Transcoding reference applications.
- [How It Works](./how-it-works.md): Understand the Video Processing Platform SDK architecture and the SVET2 application design.
- [Release Notes](./release-notes.md): Review the latest changes.

<!--hide_directive
:::{toctree}
:hidden:

./get-started
./how-it-works
Release Notes <./release-notes.md>

:::
hide_directive-->
