# Changelog

All notable changes to this project are documented in this file.

## [2025.2] - December 2025

### Added
- Introduced a new sample application for Multimodal (Vision + Timeseries) Weld Defect Detection, combining camera-based visual inspection and sensor data analysis for industrial edge insights. ([#669])
- Added fusion analytics module to combine vision and time-series anomaly detection results.
- Implemented weld data simulator for generating video streams (RTSP) and time-series data (MQTT).
- Added logger for fusion analytics and weld simulator for improved traceability. ([#777])
- Added step to enable copyleft source in build process. ([#776])
- Added architecture diagram for multimodal weld defect detection. ([#802])
- Enabled publishing of source timestamp from simulator for time-series data. ([#801])
- Added comprehensive Helm chart structure and deployment documentation for multimodal app. ([#813])
- Added "How to Deploy with Helm" section to documentation. ([#837])
- Added comprehensive troubleshooting guides covering Grafana data visibility, InfluxDB retention policies, microservice startup delays, and deployment issues. ([#1130])
- Added configurable session timeout settings for Grafana to control inactive user logout duration. ([#1000])
- Added DLStreamer pipeline server references and detailed pipeline configuration documentation. ([#1002], [#1010])

### Changed
- Updated fusion logic default mode from "AND" to "OR" for anomaly detection, improving detection flexibility. ([#794])
- Enhanced fusion analytics with additional metadata tracking, including vision classification labels.
- Redesigned Grafana dashboard layout with new fusion analytics results table and reorganized panels.
- Renamed resource folder from "weld-porosity" to "models" and updated model path to "weld-defect-classification-f16-DeiT". ([#840])
- Updated DLStreamer pipeline server image from Ubuntu 22 to Ubuntu 24.
- Modular refactoring of time series documentation for improved maintainability. ([#899])
- Multimodal apps documentation updated to use tile layout for better navigation. ([#908])
- Fixed references and broken links in documentation and toctree. ([#934], [#820])
- Fixed and enhanced documentation for Docker and Helm deployment workflows. ([#889])
- Corrected fusion analytics MQTT topic name from "fusion/anomaly" to "fusion/anomaly_detection_results".
- Updated arch diagram to remove influxdb out line from DLS PS.
- Removed references to non-existing articles in documentation. ([#924])
- Fixed dashboard name references in documentation. ([#881])
- Updated documentation for multimodal weld defect detection, transitioning from wind turbine anomaly detection theme. ([#838])
- Improved documentation clarity and consistency across files.
- Updated documentation to include DLStreamer pipeline server references and modernized system requirements. ([#1002], [#1010])
- Improved formatting and organization of multimodal documentation. ([#1035], [#1036], [#1037])
- Updated README with proper links and references. ([#1042])
- Fixed documentation issues including spelling errors, incorrect URLs, and content organization. ([#1099])
- Updated to rc1 and rc2 tag references instead of weekly releases. ([#1004], [#1129])
- Added default values for environment variables in docker-compose.yml to overcome warnings. ([#1004])
- Updated logging levels and message formatting in weld-data-simulator for improved clarity. ([#1082])
- Updated MQTT client initialization to use newer API version. ([#1082])
- Updated third-party dependency information, license attribution, package versions, and Docker image references. ([#1187])
- Updated source key extraction to check both point.tags and point.fieldsString fields in UDFs. ([#1145])
- Renamed server variable to stream_src for better clarity and introduced WELD_CURRENT_THRESHOLD constant. ([#1145])

### Removed
- Removed Helm chart deployment support for the industrial-edge-insights-multimodal sample application due to Kubernetes networking issues. Docker Compose deployment remains supported. ([#896], [#1158])
- Removed Helm deployment references from troubleshooting and getting started documentation. ([#1158])
- Hidden toctree directive in release notes and updated configuration variable documentation to reference only Docker Compose. ([#1158])

### Security
- Addressed Trivy image scan vulnerabilities by updating Python base image version and upgrading pip in all affected Dockerfiles. ([#928])
- Added SSL configuration to nginx for secure communications. ([#851])
- Enhanced container security by implementing read-only filesystem configurations and privilege restrictions across multiple Docker services (nginx_proxy, ia-fusion-analytics, dlstreamer-pipeline-server, mediamtx, coturn). ([#1149])

### Fixed
- Fixed DBS GitHub workflow by adding HOST_IP environment variable and correcting scan names. ([#916])
- Reordered CWD variable assignment in workflow scripts.
- Fixed minor documentation issues. ([#841])
- Fixed table of contents in MultiModal Weld Defect Detection documentation. ([#842])
- Fixed WebRTC publishing issues in secure mode by updating nginx configuration to properly route WHIP/WHEP traffic. ([#1089])
- Updated Grafana dashboard iframe to use HTTPS protocol with explicit port handling. ([#1089])
- Moved simulation data from Dockerfile to volume mount for optimized Weld Data Simulator container. ([#1004])
- Fixed UDF implementations for handling source key from data points. ([#1145])
- Fixed documentation issues including typos, broken links, and image references. ([#1099], [#1135])

---

[#669]: https://github.com/open-edge-platform/edge-ai-suites/commit/9a6b8011db1bdb7d91c4ce3094adde1a29767571
[#777]: https://github.com/open-edge-platform/edge-ai-suites/commit/5c156ad4581b528df01ed6fcd13f5895f15d4127
[#776]: https://github.com/open-edge-platform/edge-ai-suites/commit/0a9e14ab265d088e64e2e328ee04250bc62f36e8
[#802]: https://github.com/open-edge-platform/edge-ai-suites/commit/b08f34de976c4806bd63390cd07bde724dec592b
[#801]: https://github.com/open-edge-platform/edge-ai-suites/commit/7cc112d7f73bc40fc15e6545150dcd6154f5e7c8
[#813]: https://github.com/open-edge-platform/edge-ai-suites/commit/f4c61f3ddfb755e2704bdaae4d9ce6702c62d2e1
[#837]: https://github.com/open-edge-platform/edge-ai-suites/commit/64aa5d1e21f3c5b18cd5e059b3ea63e68492de7a
[#794]: https://github.com/open-edge-platform/edge-ai-suites/commit/16f1bd30b4100b917b07714ec1c4e4c36843865e
[#840]: https://github.com/open-edge-platform/edge-ai-suites/commit/caa379d0228e7596365a9217d922a6b75bcca43e
[#899]: https://github.com/open-edge-platform/edge-ai-suites/commit/d90aaebc5a511a2fb7455d37970d414d45c284d6
[#908]: https://github.com/open-edge-platform/edge-ai-suites/commit/f6a03a3afa2c180a268578bc0fe28575d27efafb
[#934]: https://github.com/open-edge-platform/edge-ai-suites/commit/5790e87b430e2e9b6c06bfceccefb10351b25261
[#820]: https://github.com/open-edge-platform/edge-ai-suites/commit/3350d11c555fa99ab10b1c18a090c1fa954ab9e4
[#889]: https://github.com/open-edge-platform/edge-ai-suites/commit/b28eaadffb8ef95f53d770878ff2415765b25752
[#924]: https://github.com/open-edge-platform/edge-ai-suites/commit/14e11c99007b92e54f4484a2cf2a5be675d02b24
[#881]: https://github.com/open-edge-platform/edge-ai-suites/commit/9ed010d862fdfb173ef6db7f8096fa1419cd26bf
[#838]: https://github.com/open-edge-platform/edge-ai-suites/commit/3dfefad329fa0d839b6fdd9637f3ddfc8b0fa909
[#896]: https://github.com/open-edge-platform/edge-ai-suites/commit/314492c7ca2929f826ea8f2f2376660f06986e8b
[#928]: https://github.com/open-edge-platform/edge-ai-suites/commit/307b4925f70268f97081e05c5726943775e873dc
[#851]: https://github.com/open-edge-platform/edge-ai-suites/commit/b9ab22fde4668f7ff412eff741ca1d1c880b2c85
[#916]: https://github.com/open-edge-platform/edge-ai-suites/commit/9480ed085f9807fc081a63d3239ded4066ac8423
[#841]: https://github.com/open-edge-platform/edge-ai-suites/commit/9c21e8fbdc32ebf46f8bb8e6314cfa4bee6bb31e
[#842]: https://github.com/open-edge-platform/edge-ai-suites/commit/fb37dc26b86020ce0ea256a568a2a16a8781c185
[#1000]: https://github.com/open-edge-platform/edge-ai-suites/commit/5bd639ac6ddb6a718526d6c674bb18bcb4e7f0f1
[#1002]: https://github.com/open-edge-platform/edge-ai-suites/commit/6974f43d176573dea3147b90c9da5f3cf20944a8
[#1004]: https://github.com/open-edge-platform/edge-ai-suites/commit/acb9d60139e771be75f432f778b3ab080e0befcb
[#1010]: https://github.com/open-edge-platform/edge-ai-suites/commit/6974f43d176573dea3147b90c9da5f3cf20944a8
[#1035]: https://github.com/open-edge-platform/edge-ai-suites/commit/6b9376ffba85c586cdc7cd511c6317aa4b37a5be
[#1036]: https://github.com/open-edge-platform/edge-ai-suites/commit/3b83c5efb6dd1762f9853d34af163345caad2ec4
[#1037]: https://github.com/open-edge-platform/edge-ai-suites/commit/3b83c5efb6dd1762f9853d34af163345caad2ec4
[#1042]: https://github.com/open-edge-platform/edge-ai-suites/commit/e12c57aeb7a55412e83c5bee941add50965b80bf
[#1082]: https://github.com/open-edge-platform/edge-ai-suites/commit/54a098bf320e2793d96c5645d1f5f8148bcd226b
[#1089]: https://github.com/open-edge-platform/edge-ai-suites/commit/81c43c8dd1d5f68725a7b880a68956e3abcb9e3e
[#1099]: https://github.com/open-edge-platform/edge-ai-suites/commit/8eee2a0cdd4d10f98d33068440e362c3ee0eb34a
[#1129]: https://github.com/open-edge-platform/edge-ai-suites/commit/4fc8736cda1bf2ac035993ed7e72001e38433d77
[#1130]: https://github.com/open-edge-platform/edge-ai-suites/commit/489dd1611edf8f235a7f68cf8b247a8c3ef328d4
[#1135]: https://github.com/open-edge-platform/edge-ai-suites/commit/5a67258537099aeb5a3018d50deabe6466c4decb
[#1145]: https://github.com/open-edge-platform/edge-ai-suites/commit/6ce8356e5e362db0831a3c0004c84b5ee13d16d6
[#1149]: https://github.com/open-edge-platform/edge-ai-suites/commit/4f19e57527e496ac2a9c13f11515028a616fc9d0
[#1158]: https://github.com/open-edge-platform/edge-ai-suites/commit/4e2659f30f5c78c20f8659da8db2a3225cd64d09
[#1187]: https://github.com/open-edge-platform/edge-ai-suites/commit/b61e0cada9f4a4dfb64b2b5928b7be07832f8c87