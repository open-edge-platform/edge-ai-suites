# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""LVC schema management.

Fetches the Live Video Captioning OpenAPI spec at runtime, extracts the
``StartRunRequest`` JSON Schema, resolves ``$ref`` references, adds UI
annotation hints (``x-vms-source``, ``x-format``), and builds a dynamic
Pydantic model via ``build_pydantic_from_schema``.

Keeping this logic separate means the shim stays readable and the same
pattern can be replicated for any future analytics-app integration.
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel

from plugin.common.schema_builder import build_pydantic_from_schema
from .api_client import LvcApiClient

logger = structlog.get_logger(__name__)


class LvcSchemaManager:
    """Fetches, resolves, annotates and caches the LVC parameter schema."""

    def __init__(self) -> None:
        self._dynamic_model: type[BaseModel] | None = None
        self._annotated_props: dict[str, Any] = {}  # cached annotated properties dict

    # ── Public interface ──────────────────────────────────────────────────────

    @property
    def model(self) -> type[BaseModel]:
        """Return the cached dynamic Pydantic model.

        Raises ``RuntimeError`` if :meth:`fetch` has not been called yet.
        """
        if self._dynamic_model is None:
            raise RuntimeError(
                "LVC schema not loaded. Call GET /v1/analytics-apps/discover first."
            )
        return self._dynamic_model

    @property
    def annotated_props(self) -> dict[str, Any]:
        """Return the cached annotated properties dict (empty until :meth:`fetch` succeeds)."""
        return self._annotated_props

    def get_defaults(self) -> dict[str, Any]:
        """Return a mapping of field name → default value discovered from the live LVC schema.

        Only includes fields that have an explicit ``default`` key in the OpenAPI spec.
        Returns an empty dict if the schema has not been fetched yet.
        """
        return {
            name: prop["default"]
            for name, prop in self._annotated_props.items()
            if "default" in prop and not prop.get("x-synthetic")
        }

    async def fetch(self, client: LvcApiClient) -> dict[str, Any]:
        """Fetch and process the LVC schema, returning the annotated JSON Schema dict.

        Returns the full UI schema (including synthetic ``frameResolution`` field
        and hidden ``frameWidth``/``frameHeight`` fields) to the UI.  A separate
        *model schema* — stripped of synthetic and hidden fields — is used to build
        the Pydantic model so those fields are never forwarded to LVC.

        Raises ``httpx.HTTPError`` if LVC is unreachable.
        """
        openapi = await client.get_openapi()
        schema = self._extract_start_run_schema(openapi)
        schema["properties"] = self._resolve_refs(
            schema.get("properties", {}),
            openapi.get("components", {}).get("schemas", {}),
        )
        self._annotate_fields(schema["properties"])
        self._annotated_props = dict(schema["properties"])  # cache for camera_fields()

        # Build Pydantic model from a filtered schema: exclude only synthetic UI-only fields
        # (``x-synthetic``).  Hidden fields (``x-hidden``) ARE real API fields (frameWidth,
        # frameHeight) and must remain in the model so the route can set them after expanding
        # the ``frameResolution`` composite and have them validated + forwarded to LVC.
        model_props = {
            k: v for k, v in schema["properties"].items()
            if not v.get("x-synthetic")
        }
        model_schema = {**schema, "properties": model_props}

        try:
            self._dynamic_model = build_pydantic_from_schema(model_schema, model_name="LvcStartRunParams")
            logger.info(
                "lvc_dynamic_model_built",
                fields=list(model_props.keys()),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("lvc_dynamic_model_build_failed", error=str(exc))
            self._dynamic_model = None

        return schema

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_start_run_schema(openapi: dict[str, Any]) -> dict[str, Any]:
        """Pull the StartRunRequest schema from POST /api/generate_captions_alerts in the OpenAPI spec."""
        body = openapi["paths"]["/api/generate_captions_alerts"]["post"]["requestBody"]
        schema: dict[str, Any] = body["content"]["application/json"]["schema"]

        # Resolve a top-level $ref if present
        ref = schema.get("$ref", "")
        if ref:
            model_name = ref.split("/")[-1]
            schema = openapi["components"]["schemas"][model_name]

        return schema

    @staticmethod
    def _resolve_refs(
        properties: dict[str, Any],
        components: dict[str, Any],
    ) -> dict[str, Any]:
        """Inline all ``$ref`` occurrences inside field definitions."""
        for field_name, prop in list(properties.items()):
            if "$ref" in prop:
                ref_name = prop["$ref"].split("/")[-1]
                properties[field_name] = components.get(ref_name, prop)
            elif "anyOf" in prop:
                resolved = []
                for sub in prop["anyOf"]:
                    if "$ref" in sub:
                        ref_name = sub["$ref"].split("/")[-1]
                        resolved.append(components.get(ref_name, sub))
                    else:
                        resolved.append(sub)
                properties[field_name] = {**prop, "anyOf": resolved}
        return properties

    @staticmethod
    def _annotate_fields(properties: dict[str, Any]) -> None:
        """Add UI control hints so SchemaForm renders the right widget per field.

        Annotations added:
        - ``x-vms-source: "camera-id"``    → camera dropdown (stores camera_id; backend resolves to RTSP)
        - ``x-vms-source: "lvc-models"``   → VLM model dropdown
        - ``x-vms-source: "lvc-pipelines"``→ pipeline dropdown
        - ``x-format: "textarea"``          → multi-line text area
        - ``x-format: "slider"``            → 0–1 range slider
        - ``x-hidden: true``                → field rendered by a parent composite (not shown directly)
        - ``x-synthetic: true``             → UI-only field; stripped before Pydantic validation
        """
        if "rtspUrl" in properties:
            properties["rtspUrl"] = {
                **properties["rtspUrl"],
                "title": "Camera",
                "description": "Select a discovered enabled camera.",
                "x-vms-source": "camera-id",
            }

        if "prompt" in properties:
            properties["prompt"] = {
                **properties["prompt"],
                "title": "Enter Prompt",
                "x-format": "textarea",
            }

        if "modelName" in properties:
            properties["modelName"] = {
                **properties["modelName"],
                "title": "Select Model",
                "x-vms-source": "lvc-models",
            }

        if "pipelineName" in properties:
            properties["pipelineName"] = {
                **properties["pipelineName"],
                "title": "Select Pipeline",
                "x-vms-source": "lvc-pipelines",
            }

        if "detectionThreshold" in properties:
            properties["detectionThreshold"] = {
                **properties["detectionThreshold"],
                "title": "Detection Threshold",
                "x-format": "slider",
                "x-hidden": True,
            }

        if "detectionModelName" in properties:
            properties["detectionModelName"] = {
                **properties["detectionModelName"],
                "title": "Detection Model",
                "x-hidden": True,
            }

        if "maxNewTokens" in properties:
            properties["maxNewTokens"] = {
                **properties["maxNewTokens"],
                "title": "Max New Tokens",
            }

        if "runName" in properties:
            properties["runName"] = {
                **properties["runName"],
                "title": "Run Name",
            }

        if "frameRate" in properties:
            properties["frameRate"] = {
                **properties["frameRate"],
                "title": "Frame Rate",
                "default": 1,
            }

        if "chunkSize" in properties:
            properties["chunkSize"] = {
                **properties["chunkSize"],
                "title": "Chunk Size",
                "default": 1,
            }

        # Replace raw frameWidth/frameHeight with a unified "Frame Resolution" dropdown
        # that matches LVC's own frameQualitySelect UI.  The actual integer fields are
        # hidden so they are not shown directly; the route converts the dropdown value
        # back to frameWidth/frameHeight before calling LVC.
        if "frameWidth" in properties:
            properties["frameWidth"] = {**properties["frameWidth"], "x-hidden": True}
        if "frameHeight" in properties:
            properties["frameHeight"] = {**properties["frameHeight"], "x-hidden": True}

        # Inject synthetic frameResolution field (UI-only; resolved by the route)
        properties["frameResolution"] = {
            "type": "string",
            "title": "Frame Resolution",
            "description": "Video frame resolution preset.",
            "enum": ["default", "1280x720", "640x480", "480x360"],
            "default": "default",
            "x-synthetic": True,
        }

        # Inject synthetic captionHistory field (UI-only; controls how many captions to display)
        properties["captionHistory"] = {
            "type": "integer",
            "title": "Caption History",
            "description": "Number of past captions to display in the results panel.",
            "default": 3,
            "minimum": 0,
            "x-synthetic": True,
        }
