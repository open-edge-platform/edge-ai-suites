# Release Notes: PCB Anomaly Detection

## Version 1.2.0

**March 2026**

**New**

- Qualified on the Intel® Core™ Ultra Series 3 processor.
- Added support for NPU and iGPU, for the Intel® Core™ Ultra Series 3 processor.
- Added support for simultaneous deployment of multiple applications in the same
host via Docker Compose tool and Helm chart.
- MLOps is now demonstrated with the Model Download microservice instead of
the Model Registry.
	
**Improved**

- Consumed the latest DL Streamer Pipeline Server 2026.0.0 image. Ubuntu24 variant of the image is the default now.
- Retrained the Model with Geti software v2.13.1.
- NGINX, COTURN and MINIO ports were made configurable as environment variables.
- Removed the Model Registry service and its references.

<!--hide-directive
:::{toctree}
:hidden:

Release Notes 2025 <./release-notes/release-notes-2025>

:::
hide_directive-->
