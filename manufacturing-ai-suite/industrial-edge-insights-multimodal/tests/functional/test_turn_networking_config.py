# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import subprocess
from pathlib import Path


COMPONENT_DIR = Path(__file__).resolve().parents[2]


def _run(*command: str) -> str:
    result = subprocess.run(
        command,
        cwd=COMPONENT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _helm_template() -> str:
    return _run(
        "helm",
        "template",
        "multimodal",
        "./helm",
        "--set",
        "env.INFLUXDB_USERNAME=testuser",
        "--set",
        "env.INFLUXDB_PASSWORD=testpassword1",
        "--set",
        "env.VISUALIZER_GRAFANA_USER=testuser",
        "--set",
        "env.VISUALIZER_GRAFANA_PASSWORD=testpassword1",
        "--set",
        "env.MTX_WEBRTCICESERVERS2_0_USERNAME=testuser",
        "--set",
        "env.MTX_WEBRTCICESERVERS2_0_PASSWORD=testpassword1",
        "--set",
        "env.S3_STORAGE_USERNAME=testuser",
        "--set",
        "env.S3_STORAGE_PASSWORD=testpassword1",
    )


def _compose_service_block(rendered: str, service_name: str) -> str:
    lines = rendered.splitlines()
    start = lines.index(f"  {service_name}:")
    block = []

    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("    "):
            break
        block.append(line)

    return "\n".join(block)


def test_coturn_docker_compose_uses_host_networking():
    rendered = _run("docker", "compose", "-f", "docker-compose.yml", "config")
    coturn_body = _compose_service_block(rendered, "coturn")
    assert "network_mode: host" in coturn_body
    assert "--listening-port=${COTURN_UDP_PORT}" not in coturn_body
    assert "--listening-port=3478" in coturn_body
    assert "ports:" not in coturn_body
    assert "networks:" not in coturn_body


def test_coturn_helm_template_uses_host_networking():
    rendered = _helm_template()

    coturn_deployment = next(
        doc
        for doc in rendered.split("---")
        if "kind: Deployment" in doc and "name: deployment-coturn" in doc
    )
    mediamtx_deployment = next(
        doc
        for doc in rendered.split("---")
        if "kind: Deployment" in doc and "name: deployment-mediamtx" in doc
    )

    assert "hostNetwork: true" in coturn_deployment
    assert "dnsPolicy: ClusterFirstWithHostNet" in coturn_deployment
    assert '--listening-port=3478' in coturn_deployment
    assert 'value: "turn:localhost:3478"' in mediamtx_deployment
