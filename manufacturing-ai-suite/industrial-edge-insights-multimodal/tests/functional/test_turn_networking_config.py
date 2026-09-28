# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import subprocess
from pathlib import Path

import yaml


COMPONENT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = COMPONENT_DIR / ".env"
VALUES_FILE = COMPONENT_DIR / "helm" / "values.yaml"


def _parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def _helm_values() -> dict:
    return yaml.safe_load(VALUES_FILE.read_text(encoding="utf-8"))


def _run(*command: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=COMPONENT_DIR,
        check=True,
        capture_output=True,
        env=env,
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
    env_values = _parse_dotenv(ENV_FILE)
    rendered = _run(
        "docker",
        "compose",
        "-f",
        "docker-compose.yml",
        "config",
        env={**os.environ, **env_values, "no_proxy": os.environ.get("no_proxy", "")},
    )
    coturn_body = _compose_service_block(rendered, "coturn")
    assert "network_mode: host" in coturn_body
    assert "--listening-port=${COTURN_UDP_PORT}" not in coturn_body
    assert f"--listening-port={env_values['COTURN_UDP_PORT']}" in coturn_body
    assert "ports:" not in coturn_body
    assert "networks:" not in coturn_body


def test_coturn_helm_template_uses_host_networking():
    values = _helm_values()
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
    assert "seccompProfile:" in coturn_deployment
    assert f"--listening-port={values['config']['coturn']['int']['coturn_udp_port']}" in coturn_deployment
    assert (
        f'value: "turn:{values["env"]["HOST_IP"]}:{values["config"]["coturn"]["int"]["coturn_udp_port"]}"'
        in mediamtx_deployment
    )
