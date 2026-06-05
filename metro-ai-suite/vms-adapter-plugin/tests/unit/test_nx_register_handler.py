# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for NxWitnessVmsShim.handle_register — Nx-specific registration logic."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from plugin.core.config import VmsAuthConfig, VmsInstanceConfig
from vms_shim.nxwitness.shim import NxWitnessVmsShim
from vms_shim.nxwitness.models import NxAnalyticsIntegration


_SAMPLE_MANIFESTS = {
    "integrationManifest": {
        "id": "test.integration",
        "name": "Test Integration",
        "version": "1.0.0",
    },
    "engineManifest": {
        "typeLibrary": {
            "objectTypes": [{"id": "test.obj", "name": "Object"}],
        }
    },
    "deviceAgentManifest": {"supportedTypes": []},
    "pinCode": "1234",
}


def _make_shim(manifest_path: str | None = None) -> NxWitnessVmsShim:
    config = VmsInstanceConfig(
        name="nx-main",
        vendor="nx_witness",
        base_url="https://localhost:7001",
        auth=VmsAuthConfig(username="admin", password="test"),
        analytics_manifest_path=manifest_path,
    )
    shim = NxWitnessVmsShim(config)
    shim.register_analytics = AsyncMock(return_value={
        "status": "approved",
        "username": "integration_user",
        "password": "secret",
        "request_id": "req-123",
    })
    shim.find_integration_in_vms = AsyncMock(return_value=None)
    shim.set_integration_credentials = MagicMock()
    return shim


def _make_db_record(username="cached_user", password="cached_pass") -> NxAnalyticsIntegration:
    return NxAnalyticsIntegration(
        id="some-uuid",
        vms_name="nx-main",
        analytics_app_id="test.integration",
        integration_manifest=_SAMPLE_MANIFESTS["integrationManifest"],
        engine_manifest=_SAMPLE_MANIFESTS["engineManifest"],
        nx_username=username,
        nx_password=password,
        nx_request_id="req-old",
        status="approved",
        registered_at=datetime.now(timezone.utc),
    )


def _make_upsert_result(analytics_app_id: str = "dlstreamer") -> MagicMock:
    mock = MagicMock()
    mock.model_dump = lambda **kw: {
        "vms_name": "nx-main",
        "analytics_app_id": analytics_app_id,
        "status": "approved",
        "nx_username": "integration_user",
        "nx_password": "secret",
        "nx_request_id": "req-123",
        "integration_manifest": _SAMPLE_MANIFESTS["integrationManifest"],
        "engine_manifest": _SAMPLE_MANIFESTS["engineManifest"],
        "device_agent_manifest": None,
        "registered_at": None,
    }
    return mock


async def _call_handle_register(shim, body, db_record=None, upsert_result=None, nx_record=None):
    """Helper: call handle_register with patched nx_repo."""
    mock_db = AsyncMock()
    if nx_record is not None:
        shim.find_integration_in_vms = AsyncMock(return_value=nx_record)
    with (
        patch("vms_shim.nxwitness.repository.get_nx_integration", AsyncMock(return_value=db_record)),
        patch("vms_shim.nxwitness.repository.upsert_nx_integration",
              AsyncMock(return_value=upsert_result or _make_upsert_result())),
    ):
        return await shim.handle_register(body, mock_db, "nx-main")


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_returns_cached_if_both_db_and_vms_have_it():
    """DB + Nx both have the integration → return DB record, skip registration."""
    db_record = _make_db_record()
    nx_existing = {"username": "cached_user", "password": "", "request_id": "req-old"}
    shim = _make_shim()

    result = await _call_handle_register(
        shim,
        body={"integration_manifest": _SAMPLE_MANIFESTS["integrationManifest"],
              "engine_manifest": _SAMPLE_MANIFESTS["engineManifest"]},
        db_record=db_record,
        nx_record=nx_existing,
    )

    assert result["nx_username"] == "cached_user"
    shim.register_analytics.assert_not_awaited()


async def test_raises_409_if_vms_has_it_but_db_does_not():
    """Nx has integration but DB missing → 409."""
    nx_existing = {"username": "test.integration", "password": "", "request_id": "req-nx"}
    shim = _make_shim()

    with pytest.raises(HTTPException) as exc_info:
        await _call_handle_register(
            shim,
            body={"integration_manifest": _SAMPLE_MANIFESTS["integrationManifest"],
                  "engine_manifest": _SAMPLE_MANIFESTS["engineManifest"]},
            db_record=None,
            nx_record=nx_existing,
        )

    assert exc_info.value.status_code == 409
    assert "already exists in Nx VMS but has no DB record" in exc_info.value.detail
    shim.register_analytics.assert_not_awaited()


async def test_raises_409_if_db_has_it_but_vms_does_not():
    """DB has integration but Nx missing → 409."""
    shim = _make_shim()

    with pytest.raises(HTTPException) as exc_info:
        await _call_handle_register(
            shim,
            body={"integration_manifest": _SAMPLE_MANIFESTS["integrationManifest"],
                  "engine_manifest": _SAMPLE_MANIFESTS["engineManifest"]},
            db_record=_make_db_record(),
            nx_record=None,
        )

    assert exc_info.value.status_code == 409
    assert "recorded in the DB but is missing from Nx VMS" in exc_info.value.detail
    shim.register_analytics.assert_not_awaited()


async def test_registers_with_inline_manifests():
    """Structured manifests in body trigger registration and DB upsert."""
    shim = _make_shim()
    upsert_result = _make_upsert_result("dlstreamer")

    result = await _call_handle_register(
        shim,
        body={
            "analytics_app_id": "dlstreamer",
            "integration_manifest": _SAMPLE_MANIFESTS["integrationManifest"],
            "engine_manifest": _SAMPLE_MANIFESTS["engineManifest"],
            "device_agent_manifest": _SAMPLE_MANIFESTS["deviceAgentManifest"],
            "pin_code": "1234",
        },
        upsert_result=upsert_result,
    )

    assert result["analytics_app_id"] == "dlstreamer"
    shim.register_analytics.assert_awaited_once()
    called_manifest = shim.register_analytics.call_args[0][0]
    assert called_manifest["integrationManifest"]["id"] == "test.integration"
    assert called_manifest["pinCode"] == "1234"


async def test_registers_with_manifest_file_path(tmp_path):
    """Manifest loaded from analytics_manifest_path when no inline manifests."""
    manifest_file = tmp_path / "nx_manifest.json"
    manifest_file.write_text(json.dumps(_SAMPLE_MANIFESTS))
    shim = _make_shim(manifest_path=str(manifest_file))

    result = await _call_handle_register(shim, body={"manifest": {}})

    assert result["status"] == "approved"
    shim.register_analytics.assert_awaited_once()


async def test_registers_with_bundled_default_when_no_manifest_path():
    """No manifest in body and no config path → bundled nx_integration.json is used."""
    shim = _make_shim(manifest_path=None)

    result = await _call_handle_register(shim, body={"manifest": {}})

    shim.register_analytics.assert_awaited_once()


async def test_raises_422_if_manifest_file_not_found():
    """analytics_manifest_path points to non-existent file → 422."""
    shim = _make_shim(manifest_path="/does/not/exist.json")

    with pytest.raises(HTTPException) as exc_info:
        await _call_handle_register(shim, body={"manifest": {}})

    assert exc_info.value.status_code == 422


async def test_sets_integration_credentials_on_fresh_registration():
    """Fresh registration calls set_integration_credentials so push works immediately."""
    shim = _make_shim()

    await _call_handle_register(
        shim,
        body={
            "analytics_app_id": "dlstreamer",
            "integration_manifest": _SAMPLE_MANIFESTS["integrationManifest"],
            "engine_manifest": _SAMPLE_MANIFESTS["engineManifest"],
        },
    )

    shim.set_integration_credentials.assert_called_once_with("integration_user", "secret")


async def test_raises_502_when_shim_returns_error_status():
    """register_analytics returning status=error → 502."""
    shim = _make_shim()
    shim.register_analytics = AsyncMock(return_value={
        "status": "error",
        "reason": "create_integration_request_failed",
    })

    with pytest.raises(HTTPException) as exc_info:
        await _call_handle_register(
            shim,
            body={
                "integration_manifest": _SAMPLE_MANIFESTS["integrationManifest"],
                "engine_manifest": _SAMPLE_MANIFESTS["engineManifest"],
            },
        )

    assert exc_info.value.status_code == 502
    assert "create_integration_request_failed" in exc_info.value.detail
