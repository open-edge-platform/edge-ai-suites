# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Functional test map — industrial-edge-insights-multimodal

All files live in `tests/functional/`. Install deps first:

```bash
cd tests/functional
python3 -m venv env && source env/bin/activate
pip3 install -r ../requirements.txt
```

| File | Deployment method | Hardware | Notes |
|---|---|---|---|
| `test_docker_deployment_multimodal.py` | Docker Compose | CPU | Primary functional smoke/deploy test |
| `test_GPU_docker_multimodal.py` | Docker Compose | GPU | Marked `gpu`; requires `/dev/dri` |
| `test_NPU_docker_multimodal.py` | Docker Compose | NPU | Requires `/dev/accel` |
| `test_helm_deployment_multimodal.py` | Helm | CPU | Primary Helm deploy test |
| `test_GPU_helm_multimodal.py` | Helm | GPU | Marked `gpu`; needs `privileged_access_required=true` install |
| `test_NPU_helm_multimodal.py` | Helm | NPU | Needs `privileged_access_required=true` install |

Markers available (see `pytest.ini`): `kpi`, `docker_security`, `longrun`,
`gpu`. Example selective run: `pytest -v -s -m gpu test_GPU_docker_multimodal.py`.

Reports: pass `--html=<name>.html` to get an HTML report; always summarize
PASS/FAIL counts from the pytest console output in your answer, don't just
point at the report file.
