# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Configuration management :YAML + Pydantic Settings with env var resolution."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from analytics_app_shim.lvc.config import LiveCaptioningAnalyticsAppConfig  # noqa: F401
from analytics_app_shim.object_detection.config import ObjectDetectionAnalyticsAppConfig  # noqa: F401


_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)(?::-(.*?))?\}")


def _resolve_env_vars(value: str) -> str:
    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(2)
        env_val = os.environ.get(var_name)
        if env_val is None:
            if default is not None:
                return default
            print(
                f"FATAL: environment variable '{var_name}' is not set "
                f"but is referenced in config.yaml",
                file=sys.stderr,
            )
            sys.exit(1)
        return env_val
    return _ENV_VAR_PATTERN.sub(_replacer, value)


def _resolve_recursive(obj):
    if isinstance(obj, str):
        return _resolve_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _resolve_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_recursive(item) for item in obj]
    return obj


class VmsAuthConfig(BaseModel):
    """VMS auth credentials.

    The plugin **facilitates** auth — it does not maintain long-lived sessions.
    Credentials here are used only when calling the VMS during
    discover/register/write-back. Per-request token pass-through from the
    App is left as a v2 hook.
    """
    username: str = ""
    password: str = ""
    auth_type: Literal["basic", "digest", "none"] = "none"


class VmsInstanceConfig(BaseModel):
    name: str
    vendor: str
    base_url: str = ""
    tls_verify: bool = False
    tls_ca_bundle: str = ""
    auth: VmsAuthConfig = Field(default_factory=VmsAuthConfig)
    # Path to a JSON file containing Nx analytics integration manifests.
    # Expected keys: integrationManifest, engineManifest, deviceAgentManifest, pinCode.
    # Used only by the nx_witness vendor.
    analytics_manifest_path: str | None = None

    @field_validator("vendor")
    @classmethod
    def _validate_vendor(cls, v: str) -> str:
        # Lazy import to avoid circular dependency (factory imports config)
        from plugin.core.factory import _VMS_REGISTRY
        known = set(_VMS_REGISTRY.keys())
        if v not in known:
            raise ValueError(f"Unknown vendor '{v}'. Registered vendors: {sorted(known)}")
        return v



AnyCorAppConfig = LiveCaptioningAnalyticsAppConfig | ObjectDetectionAnalyticsAppConfig

# Discriminated union for Pydantic to pick the right config model from the YAML `type` field.
_DiscriminatedAnalyticsAppConfig = Annotated[
    LiveCaptioningAnalyticsAppConfig | ObjectDetectionAnalyticsAppConfig,
    Field(discriminator="type"),
]


class MqttConfig(BaseModel):
    host: str = ""
    port: int = 1883


class ApiConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    api_key: str = ""


class DatabaseConfig(BaseModel):
    url: str = "postgresql+asyncpg://vms:vms@localhost:5432/vms_plugin"


class LoggingConfig(BaseModel):
    level: str = "info"


class AppConfig(BaseModel):
    vms_instances: list[VmsInstanceConfig] = Field(default_factory=list)
    analytics_apps: list[_DiscriminatedAnalyticsAppConfig] = Field(default_factory=list)  # type: ignore[valid-type]
    api: ApiConfig = Field(default_factory=ApiConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    mqtt: MqttConfig = Field(default_factory=MqttConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @model_validator(mode="before")
    @classmethod
    def resolve_env_vars(cls, values):
        values = _resolve_recursive(values)
        if isinstance(values, dict) and "analytics_app" in values and "analytics_apps" not in values:
            legacy = values.pop("analytics_app")
            values["analytics_apps"] = [legacy] if legacy else []
        return values

    @property
    def analytics_app(self) -> "AnyCorAppConfig | None":
        return self.analytics_apps[0] if self.analytics_apps else None


class Settings(BaseSettings):
    config_path: str = "/app/config/config.yaml"
    database_url: str = ""
    model_config = {"env_prefix": "VMS_PLUGIN_"}


def load_config(path: str | Path | None = None) -> AppConfig:
    try:
        from dotenv import load_dotenv
        _env_file = Path(".env")
        if _env_file.exists():
            load_dotenv(dotenv_path=_env_file, override=False)
    except ImportError:
        pass

    settings = Settings()
    config_path = Path(path) if path else Path(settings.config_path)
    if not config_path.exists():
        print(f"FATAL: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    config = AppConfig(**raw)

    # VMS_PLUGIN_DATABASE_URL, when set, takes precedence over the value
    # resolved from config.yaml so operators can override it without editing
    # the config file (e.g. in docker-compose.yml).
    if settings.database_url:
        config.database.url = settings.database_url

    return config
