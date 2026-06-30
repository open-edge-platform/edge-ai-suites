# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Factory that builds the Nx Witness ``deviceAgentSettingsModel`` from config.

The bundled ``nx_integration.json`` is kept generic (empty settings items). The
per-camera settings panel shown in the Nx Witness client is generated at startup
from the analytics apps listed in ``config.yaml`` — one field group per app.

Design
──────
* **Field providers, keyed by app type.** Each analytics app contributes its own
  Nx settings items. The default provider reads them from the app config's
  ``nx_settings_fields()`` method, so app-specific fields live with the app and
  require no edits to the Nx manifest.
* **Registry for overrides.** Register a custom provider via
  :func:`register_settings_provider` when an app needs bespoke field-building
  logic beyond what its config exposes.
* **Single vs. multiple apps.** With one app the fields stay flat for
  backward compatibility. With several apps each app's fields are wrapped in a
  ``GroupBox`` captioned with its ``display_name`` and the field names are
  namespaced as ``<app_id>.<field>`` so they never collide.

Adding a new app to ``config.yaml`` is enough to make it appear in the Nx UI; no
changes here are needed unless it requires a custom provider.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

import structlog

logger = structlog.get_logger(__name__)


class _AppSettingsConfig(Protocol):
    """Minimal shape a config must expose to contribute settings fields."""

    app_id: str
    display_name: str

    def nx_settings_fields(self) -> list[dict]: ...


# A provider turns one analytics-app config into a flat list of Nx settings items.
SettingsProvider = Callable[[Any], list[dict]]

# type → provider. Apps not listed fall back to ``_default_provider``.
_PROVIDER_REGISTRY: dict[str, SettingsProvider] = {}


def register_settings_provider(app_type: str, provider: SettingsProvider) -> None:
    """Register a custom settings-field provider for an analytics app ``type``."""
    _PROVIDER_REGISTRY[app_type] = provider


def _default_provider(cfg: Any) -> list[dict]:
    """Default provider: ask the config for its fields, or contribute nothing."""
    fields = getattr(cfg, "nx_settings_fields", None)
    return list(fields()) if callable(fields) else []


def _fields_for(cfg: Any) -> list[dict]:
    provider = _PROVIDER_REGISTRY.get(getattr(cfg, "type", ""), _default_provider)
    return provider(cfg)


def build_device_agent_settings_model(app_configs: list[Any]) -> dict:
    """Build the Nx ``deviceAgentSettingsModel`` from configured analytics apps.

    Returns a dict ``{"type": "Settings", "items": [...]}`` ready to drop into
    ``engineManifest.deviceAgentSettingsModel``. Apps contributing no fields are
    skipped. Empty input yields an empty (but valid) settings model.
    """
    contributing = [(cfg, _fields_for(cfg)) for cfg in app_configs]
    contributing = [(cfg, items) for cfg, items in contributing if items]

    if not contributing:
        return {"type": "Settings", "items": []}

    if len(contributing) == 1:
        # Single app: keep field names flat for backward compatibility.
        return {"type": "Settings", "items": contributing[0][1]}

    # Multiple apps: one GroupBox per app, namespaced field names to avoid clashes.
    items: list[dict] = []
    for cfg, fields in contributing:
        app_id = getattr(cfg, "app_id", "")
        namespaced = []
        for field in fields:
            item = dict(field)
            if app_id and item.get("name"):
                item["name"] = f"{app_id}.{item['name']}"
            namespaced.append(item)
        items.append({
            "type": "GroupBox",
            "name": app_id or getattr(cfg, "type", "app"),
            "caption": getattr(cfg, "display_name", "") or app_id,
            "items": namespaced,
        })
    return {"type": "Settings", "items": items}


def apply_settings_model(manifests: dict, app_configs: list[Any]) -> None:
    """Populate ``engineManifest.deviceAgentSettingsModel`` in-place from config."""
    model = build_device_agent_settings_model(app_configs)
    (
        manifests
        .setdefault("engineManifest", {})
    )["deviceAgentSettingsModel"] = model
    logger.info("nx_settings_model_built", apps=len(app_configs), items=len(model["items"]))
