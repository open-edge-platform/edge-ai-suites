# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Configuration model for the Live Video Captioning analytics app shim."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class LiveCaptioningAnalyticsAppConfig(BaseModel):
    type: Literal["live_captioning"] = "live_captioning"
    app_id: str = "live_captioning"
    display_name: str = "Live Video Captioning"
    base_url: str
    mediamtx_url: str = ""
    # Default LVC pipeline name.  Leave empty to let VAP resolve the first
    # available pipeline from the LVC OpenAPI spec at run time.
    pipeline_name: str = ""

    def control_params(self) -> list[dict]:
        """Declare this app's per-camera control knobs (VMS-neutral).

        A ``bool`` named ``pipelineEnabled`` is the start/stop toggle; ``device``
        selects the inference device; ``prompt`` is an optional free-text prompt.
        A VMS shim renders these into its own UI.
        """
        return [
            {
                "name": "pipelineEnabled",
                "type": "bool",
                "default": False,
                "label": f"Enable {self.display_name} Pipeline",
                "description": f"Start or stop the {self.display_name} pipeline for this camera",
            },
            {
                "name": "device",
                "type": "enum",
                "default": "CPU",
                "options": ["CPU", "GPU", "NPU"],
                "label": "Device",
                "description": "Inference device for the vision-language model",
            },
            {
                "name": "prompt",
                "type": "text",
                "default": "",
                "label": "Prompt",
                "description": "Custom prompt sent to the vision-language model. Leave empty to use the LVC application default.",
            },
        ]
