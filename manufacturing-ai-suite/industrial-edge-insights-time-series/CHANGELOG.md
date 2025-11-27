# Changelog

All notable changes to this project are documented in this file.

## [2025.2] - December 2025

### Added
- Integrated new "Weld Anomaly Detection" sample application with CatBoost ML model and dashboards. ([#742])
- Enabled scaling for OPC-UA ingestion in wind turbine sample app via Docker Compose and updated telegraf config generation. ([#732])
- Added GPU inferencing support for both Docker Compose and Helm deployments. ([#718])
- Added Nginx as a reverse proxy with Helm template support, including SSL certificate generation and MQTT proxy configuration. ([#705])
- Added legends to Grafana graphs for weld anomaly detection. ([#839])
- Added updated architecture diagram for 2025.2 release. ([#800])
- Added logger for fusion analytics and weld simulator. ([#777])
- Added installation of requirements.txt for Python packages in venv for Ubuntu 24.04 compatibility. ([#804])
- Added .gitignore file for improved repo hygiene. ([#791])
- Added comprehensive documentation and visualization dashboards for weld sensor data.
- Added comprehensive troubleshooting guides covering Grafana data visibility, InfluxDB retention policies, microservice startup delays, and Helm deployment issues. ([#1130])
- Added support for source key to identify individual MQTT streams in multi-stream deployment scenarios with INSTANCE_ID environment variable. ([#1119])
- Added configurable session timeout settings for Grafana to control inactive user logout duration. ([#1000])
- Added comprehensive documentation for connecting to external secure OPC UA servers with TLS/SSL encryption. ([#976])

### Changed
- Migrated from Bitnami/nginx to official nginx image for enhanced security and compatibility. ([#726])
- Changed internal HTTPS port for nginx from 443 to 15443 to comply with Kubernetes security policies. ([#741])
- Updated build system to support multiple sample applications via app parameter.
- Updated hardcoded localhost references to dynamic host_ip placeholders in documentation. ([#888])
- Updated Grafana dashboard to display processing times in seconds instead of milliseconds. ([#897])
- Updated influx query and measurement/table names for accuracy. ([#695])
- Updated arch diagram to drawio UX template. ([#800])
- Updated docs to pull Helm charts for rc1 and rc2 tags. ([#721], [#1003], [#1129])
- Updated Helm docs to download artifacts for sample apps. ([#766])
- Updated Python script execution to use virtual environment.
- Updated volume mounts in Docker Compose and Helm charts for unified configs folder. ([#781])
- Updated fusion analytics MQTT topic name and improved comment formatting. ([#889])
- Restructured alert configuration headings to distinguish Docker vs Helm deployment. ([#888])
- Modular refactoring of time series documentation for maintainability.
- Updated third-party dependency information, license attribution, package versions, and Docker image references. ([#1187])
- Updated Helm deployment documentation with absolute public documentation URLs and explicit version parameters. ([#1183])
- Updated source key extraction to check both point.tags and point.fieldsString fields in UDFs. ([#1145])
- Renamed server variable to stream_src for better clarity and introduced WELD_CURRENT_THRESHOLD constant. ([#1145])
- Updated OPC UA volume mount configuration from dynamic to static in deployment template. ([#1008])
- Changed Kubernetes Service type from NodePort to ClusterIP for time-series-analytics-microservice and Grafana. ([#1104])
- Restructured time series documentation for improved navigation and clarity. ([#1022])

### Removed
- Removed Model Registry related code and docs from sample apps. ([#769])

### Fixed
- Fixed missing Python package installation for fresh systems. ([#791])
- Fixed path and port issues in documentation and configuration files. ([#740])
- Fixed table of contents in wind turbine documentation. ([#806])
- Fixed minor documentation bugs and improved clarity. ([#695], [#888])
- Fixed missing version parameter in Helm charts for weld anomaly detection. ([#863])
- Fixed documentation issues including typos, broken links, and image references across time-series component. ([#1101])
- Fixed MQTT publisher continuous ingestion loop to properly cycle through CSV files. ([#1098])
- Fixed UDF implementations for handling source key from data points. ([#1145])
- Fixed table of contents and image references in documentation. ([#1115], [#1111], [#1136])

### Security
- Added SSL/TLS protocol restrictions and cipher configurations to nginx. ([#847], [#851])
- Implemented security headers (HSTS, X-Frame-Options, etc.) and proxy buffering limits in nginx. ([#847])
- Addressed Trivy image scan vulnerabilities by updating Python base image and pip in Dockerfiles. ([#928])
- Enhanced container security by implementing read-only filesystem configurations and privilege restrictions across multiple Docker services. ([#1149])
- Addressed nmap port security issues by changing Service types from NodePort to ClusterIP. ([#1104])

---

[#742]: https://github.com/open-edge-platform/edge-ai-suites/commit/adce01b6468752154da9fd477337a045e33eed42
[#732]: https://github.com/open-edge-platform/edge-ai-suites/commit/03d67d5fc97361d858e92e749a3d76ce12882074
[#718]: https://github.com/open-edge-platform/edge-ai-suites/commit/b5f19b19a279aea6cfd5e202ee421075bf467c1d
[#705]: https://github.com/open-edge-platform/edge-ai-suites/commit/343f832c0e32cacd38417ae8032496067ff9bdb0
[#839]: https://github.com/open-edge-platform/edge-ai-suites/commit/9e8330475d0b10a5fa257b82c15ba4e2addbe299
[#800]: https://github.com/open-edge-platform/edge-ai-suites/commit/4dadcb69937e68a42fa83baa8aad97b0b8592b96
[#777]: https://github.com/open-edge-platform/edge-ai-suites/commit/5c156ad4581b528df01ed6fcd13f5895f15d4127
[#804]: https://github.com/open-edge-platform/edge-ai-suites/commit/8c946ff3857d159f64aa49ec56c326211ddd2c08
[#791]: https://github.com/open-edge-platform/edge-ai-suites/commit/ac4fba464a8406983a4ea80a3a28a4e420356d41
[#726]: https://github.com/open-edge-platform/edge-ai-suites/commit/931fef94fbf6295bcbfd1952cd307d9ee02d8ac6
[#741]: https://github.com/open-edge-platform/edge-ai-suites/commit/37cdcdf97f476e67f1e3b720953cf37b944e9a56
[#888]: https://github.com/open-edge-platform/edge-ai-suites/commit/1c110bbf5427616a01f30cc12e3d44369e289ad3
[#897]: https://github.com/open-edge-platform/edge-ai-suites/commit/f3ad24b7420d5f8043fa303ce3aa145626a8f7a2
[#695]: https://github.com/open-edge-platform/edge-ai-suites/commit/bf232d19b68b870c40c7252dd1c37f34c2bc7f60
[#721]: https://github.com/open-edge-platform/edge-ai-suites/commit/a1c6aaecc147306d9ae92c3f0f028e70263eed18
[#766]: https://github.com/open-edge-platform/edge-ai-suites/commit/5763626d628cf567cb46f9d2c9cec2a98d4ac3d5
[#781]: https://github.com/open-edge-platform/edge-ai-suites/commit/f0c548ab64421c25b16d8293790042e1686bc689
[#769]: https://github.com/open-edge-platform/edge-ai-suites/commit/451d41020b674b102edb4d9e882091773b71db0d
[#740]: https://github.com/open-edge-platform/edge-ai-suites/commit/dc826ae0e0019b16998f32c615dedd38826a1958
[#806]: https://github.com/open-edge-platform/edge-ai-suites/commit/43d848dabb494d65f86f36db426f2563e272d696
[#863]: https://github.com/open-edge-platform/edge-ai-suites/commit/de96f388ab6770f05aa65d22e9f40d489607075c
[#847]: https://github.com/open-edge-platform/edge-ai-suites/commit/6d6e18dab3780b09b6a8f76ecbf194d081111c0d
[#851]: https://github.com/open-edge-platform/edge-ai-suites/commit/b9ab22fde4668f7ff412eff741ca1d1c880b2c85
[#928]: https://github.com/open-edge-platform/edge-ai-suites/commit/307b4925f70268f97081e05c5726943775e873dc
[#976]: https://github.com/open-edge-platform/edge-ai-suites/commit/35acee9a5958289012664262feab7f664703c977
[#1000]: https://github.com/open-edge-platform/edge-ai-suites/commit/5bd639ac6ddb6a718526d6c674bb18bcb4e7f0f1
[#1003]: https://github.com/open-edge-platform/edge-ai-suites/commit/be065a698e2cdb6cfe9f3dbf3654bd0290af5b30
[#1008]: https://github.com/open-edge-platform/edge-ai-suites/commit/9e3917c0f01112aef858959d3daafe1f4ebc79a0
[#1022]: https://github.com/open-edge-platform/edge-ai-suites/commit/3f9cbd6dd8daf7fca309446ea055fef8e6e38849
[#1098]: https://github.com/open-edge-platform/edge-ai-suites/commit/fc1cbecff296a3592dbd22a9942af88556d1055b
[#1101]: https://github.com/open-edge-platform/edge-ai-suites/commit/2e8c5be0e742adc844181b1d75708dd912dc436b
[#1104]: https://github.com/open-edge-platform/edge-ai-suites/commit/42689214062a6d7d1c78d8faa3981d241d507a7d
[#1111]: https://github.com/open-edge-platform/edge-ai-suites/commit/1152b4ead610d41f4e9cf1a6b0aac826d755c858
[#1115]: https://github.com/open-edge-platform/edge-ai-suites/commit/97f3371ef16e500fc81836ce853011909bd03a5a
[#1119]: https://github.com/open-edge-platform/edge-ai-suites/commit/9214c489a7c7236fb0b3a66ea31685fed65be85c
[#1129]: https://github.com/open-edge-platform/edge-ai-suites/commit/4fc8736cda1bf2ac035993ed7e72001e38433d77
[#1130]: https://github.com/open-edge-platform/edge-ai-suites/commit/489dd1611edf8f235a7f68cf8b247a8c3ef328d4
[#1136]: https://github.com/open-edge-platform/edge-ai-suites/commit/038126b5b313cfe0492d30310cebb64442d85a78
[#1145]: https://github.com/open-edge-platform/edge-ai-suites/commit/6ce8356e5e362db0831a3c0004c84b5ee13d16d6
[#1149]: https://github.com/open-edge-platform/edge-ai-suites/commit/4f19e57527e496ac2a9c13f11515028a616fc9d0
[#1183]: https://github.com/open-edge-platform/edge-ai-suites/commit/655f170f1dff498a727c213927aa7295358d61fe
[#1187]: https://github.com/open-edge-platform/edge-ai-suites/commit/b61e0cada9f4a4dfb64b2b5928b7be07832f8c87