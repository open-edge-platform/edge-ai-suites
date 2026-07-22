# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Configuration model for the Object Detection (DLStreamer Pipeline Server) analytics app shim."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ObjectDetectionAnalyticsAppConfig(BaseModel):
    """Config for DLStreamer Pipeline Server–based object detection apps (e.g. Loitering Detection)."""

    type: Literal["object_detection"] = "object_detection"
    # Identifies this app instance in API URLs (e.g. "dls_vision" → /v1/analytics-apps/dls_vision/runs)
    app_id: str = "dls_vision"
    display_name: str = "Object Detection"
    base_url: str  # Pipeline Server REST URL
    tls_verify: bool = False
    tls_ca_bundle: str = ""
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_tls_enabled: bool = False
    mqtt_ca_bundle: str = ""
    mqtt_client_cert: str = ""
    mqtt_client_key: str = ""
    # Broker address as seen by the Pipeline Server (used in the destination payload
    # so gvametapublish can connect). Defaults to the Pipeline Server's MQTT_HOST env var
    # value (container name on the DLStreamer Vision network). Set to "host.docker.internal" if the
    # broker is only reachable via the host's published port.
    pipeline_server_mqtt_host: str = "mqtt-broker"
    pipeline_server_mqtt_port: int = 1883
    # Maps detection labels (case-insensitive) to Nx Witness object typeIds.
    # Any label not present here falls back to "python.detected.object".
    # These typeIds are also merged into the Nx analytics manifest at startup
    # so that Nx accepts pushed objects for all configured types.
    # Example:
    #   label_type_map:
    #     car: vap.vehicle
    #     truck: vap.vehicle
    #     person: vap.person
    #     forklift: custom.forklift
    label_type_map: dict[str, str] = Field(default_factory=dict)
    # Compensates for the delay between frame capture and MQTT message arrival
    # (inference latency + pipeline overhead). A negative value shifts the pushed
    # metadata timestamp backward so it aligns with the corresponding video frame
    # in Nx. For example, -300 corrects for ~300 ms of inference latency.
    # Has no effect when sender_ntp_unix_timestamp_ns is present in the payload.
    metadata_timestamp_offset_ms: int = 0
    # DLS pipeline name to be run. This is populated from config/config.yaml
    pipeline_name: str = ""
    def object_types(self) -> list[str]:
        """Return the object type ids this app emits (VMS-neutral).

        Derived from ``label_type_map`` values so a VMS shim can register them
        generically, without knowing this app exists. Apps that do not push
        object detections simply omit this method.
        """
        return sorted(set(self.label_type_map.values()))

    def control_params(self) -> list[dict]:
        """Declare this app's per-camera control knobs (VMS-neutral).

        A ``bool`` named ``pipelineEnabled`` is the start/stop toggle; ``device``
        selects the inference device. A VMS shim renders these into its own UI.
        """
        return [
            {
                "name": "pipelineEnabled",
                "type": "bool",
                "default": False,
                "label": f"Enable {self.display_name} pipeline",
                "description": f"Start or stop the {self.display_name} pipeline for this camera",
            },
            {
                "name": "device",
                "type": "enum",
                "default": "CPU",
                "options": ["CPU", "GPU", "NPU"],
                "label": "Device",
                "description": "Inference device for the pipeline",
            },
        ]

