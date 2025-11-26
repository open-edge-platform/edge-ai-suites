# Container Images

## MQTT Publisher Simulator

The MQTT publisher simulator extracts weld/wind turbine data from a CSV file(s) and sends it as a JSON-formatted data over the configured topic to the MQTT broker. The Telegraf MQTT input plugin then subscribes to this topic to receive the weld/wind turbine data.

The MQTT publisher simulator is used for ingesting the weld data and wind turbine data in the `Weld Anomaly Detection Sample App` and `Wind Turbine Anomaly Detection Sample App` respectively.

## OPC-UA Server Simulator

The OPC-UA server simulator acts as a dummy OPC-UA server creating the nodes for the wind turbine data by reading from the CSV file and writing the data to the OPC-UA input plugin in Telegraf. The OPC-UA server simulator if configured in Time Series Analytics microservice can act as data destination for receiving the anomaly alerts.

The OPC-UA server simulator is used for ingesting the wind turbine data in the `Wind Turbine Anomaly Detection Sample App`.

## Supported Versions

> **Note**: The tags suffixed with `-weekly` and `-rcX` are developmental builds, may not be stable.

### [1.1.0](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/ai-suite-manufacturing/industrial-edge-insights-time-series/release_notes.html#v2025-2-december-2025)

#### Deploy using Docker Compose

For more details on deployment, refer to the [documentation](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/ai-suite-manufacturing/industrial-edge-insights-time-series/get-started.html).

#### Deploy on Kubernetes cluster using Helm Charts

For more details on deployment, refer to the [documentation](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/ai-suite-manufacturing/industrial-edge-insights-time-series/how-to-guides/how-to-deploy-with-helm.html).

### [1.0.0](https://docs.openedgeplatform.intel.com/2025.1/edge-ai-suites/wind-turbine-anomaly-detection/release_notes/aug-2025.html#v1-0-0)

#### Deploy using Docker Compose

For more details on deployment, refer to the [documentation](https://docs.openedgeplatform.intel.com/2025.1/edge-ai-suites/wind-turbine-anomaly-detection/get-started.html).

#### Deploy on Kubernetes cluster using Helm Charts

For more details on deployment, refer to the [documentation](https://docs.openedgeplatform.intel.com/2025.1/edge-ai-suites/wind-turbine-anomaly-detection/how-to-deploy-with-helm.html).

## License Agreement

Copyright (C) 2024 Intel Corporation.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

## Legal Information

Intel, the Intel logo, and Xeon are trademarks of Intel Corporation in the U.S. and/or other countries.

*Other names and brands may be claimed as the property of others.
