# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Functional test map — industrial-edge-insights-time-series

All files live in `tests/functional/`. Install deps first:

```bash
cd tests/functional
python3 -m venv env && source env/bin/activate
pip3 install -r ../requirements.txt
```

| File | Deployment method | Scenario |
|---|---|---|
| `test_docker_deployment_wind_turbine.py` | Docker Compose | Primary functional deploy test |
| `test_docker_influxdb_retention.py` | Docker Compose | InfluxDB retention policy check |
| `test_docker_deployment_stability.py` | Docker Compose | Marked `longrun`; extended stability run |
| `test_GPU_docker.py` | Docker Compose | Marked `gpu`; requires `/dev/dri` |
| `test_helm_deployment_wind_turbine.py` | Helm | Primary Helm deploy test |
| `test_helm_influxdb_retention.py` | Helm | InfluxDB retention policy check (Helm) |
| `test_GPU_helm.py` | Helm | Marked `gpu`; needs `privileged_access_required=true` install |
| `test_docker_helm_deployment_security.py` | Either (already running) | Marked `docker_security`; security checks against either deployment |

Markers available (see `pytest.ini`): `kpi`, `mqtt`, `opcua`,
`docker_security`, `longrun`, `gpu`. Example: select only MQTT-path tests with
`pytest -v -s -m mqtt`.

Reports: pass `--html=<name>.html` to get an HTML report; always summarize
PASS/FAIL counts from the pytest console output in your answer, don't just
point at the report file.
