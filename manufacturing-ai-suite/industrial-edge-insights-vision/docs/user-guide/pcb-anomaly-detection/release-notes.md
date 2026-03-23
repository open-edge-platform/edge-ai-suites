# Release Notes: PCB Anomaly Detection

## Version 1.2.0

**March 2026**

- Added support for NPU and iGPU for Intel Core Ultra Series 3 processors.
- Added support for simultaneous deployment of multiple applications in the same host via Docker and Helm.
- MLOps is now demonstrated with the Model Download microservice instead of Model Registry.
- The NGINX, COTURN and MINIO ports made configurable as environment variables.
- Consumed the latest DL Streamer Pipeline Server 2026.0.0 image.
  The Ubuntu24 variant of the image is now default.

**Improved**

- The model retrained with Geti v2.13.1.
- Removed the Model Registry service and its references.

<!--hide-directive
:::{toctree}
:hidden:

Release Notes 2025 <./release-notes/release-notes-2025>

:::
hide_directive-->
