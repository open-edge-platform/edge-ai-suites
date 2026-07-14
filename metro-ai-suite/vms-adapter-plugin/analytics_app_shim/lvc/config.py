# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Configuration model for the Live Video Captioning analytics app shim."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LiveCaptioningAnalyticsAppConfig(BaseModel):
    type: Literal["live_captioning"] = "live_captioning"
    app_id: str = "live_captioning"
    display_name: str = "Live Video Captioning"
    base_url: str
    mediamtx_url: str = ""
    # Default LVC pipeline name.  Leave empty to let VAP resolve the first
    # available pipeline from the LVC OpenAPI spec at run time.
    pipeline_name: str = ""
    # Fields to display in the Nx Witness device-agent settings panel.
    # Each entry is a raw Nx settings item dict (type, name, caption, …).
    # When non-empty these fully replace the built-in defaults below.
    display_fields: list[dict] = Field(default_factory=list)

    def nx_settings_fields(self) -> list[dict]:
        """Return Nx device-agent settings items for the LVC camera panel.

        Returns ``display_fields`` from config.yaml when set, otherwise the
        built-in defaults: an enable checkbox, a device dropdown, and a
        free-text prompt field.
        """
        if self.display_fields:
            return self.display_fields
        return [
            {
                "type": "CheckBox",
                "name": "pipelineEnabled",
                "caption": f"Enable {self.display_name} Pipeline",
                "description": (
                    f"Start or stop the {self.display_name} pipeline for this camera"
                ),
                "defaultValue": False,
            },
            {
                "type": "ComboBox",
                "name": "device",
                "caption": "Device",
                "description": "Inference device for the vision-language model",
                "defaultValue": "CPU",
                "range": ["CPU", "GPU", "NPU"],
            },
            {
                "type": "TextField",
                "name": "prompt",
                "caption": "Prompt",
                "description": (
                    "Custom prompt sent to the vision-language model. "
                    "Leave empty to use the LVC application default."
                ),
                "defaultValue": "",
            },
        ]
