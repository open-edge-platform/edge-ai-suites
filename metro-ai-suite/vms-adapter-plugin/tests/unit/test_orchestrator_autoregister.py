# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for NxWitnessVmsShim.on_startup credential restore."""

from __future__ import annotations

import json
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plugin.core.pipeline.orchestrator import Orchestrator
from plugin.core.config import AppConfig, VmsAuthConfig, VmsInstanceConfig, DatabaseConfig, ApiConfig
from vms_shim.nxwitness.shim import NxWitnessVmsShim


_SAMPLE_MANIFESTS = {
    "integrationManifest": {"id": "dls_vision", "name": "DLStreamer Vision", "version": "1.0.0"},
    "engineManifest": {"typeLibrary": {"objectTypes": []}},
    "pinCode": "1234",
}


def _make_config(manifest_path: str) -> AppConfig:
    return AppConfig(
        vms_instances=[
            VmsInstanceConfig(
                name="nx-main",
                vendor="nx_witness",
                base_url="https://localhost:7001",
                auth=VmsAuthConfig(username="admin", password="pass"),
                analytics_manifest_path=manifest_path,
            )
        ],
        analytics_apps=[],
        database=DatabaseConfig(url="postgresql+asyncpg://vms:vms@localhost/vms"),
        api=ApiConfig(),
    )


def _make_shim(manifest_path: str = "", nx_record=None) -> NxWitnessVmsShim:
    config = VmsInstanceConfig(
        name="nx-main",
        vendor="nx_witness",
        base_url="https://localhost:7001",
        auth=VmsAuthConfig(username="admin", password="pass"),
        analytics_manifest_path=manifest_path,
    )
    shim = NxWitnessVmsShim(config)
    shim.find_integration_in_vms = AsyncMock(return_value=nx_record)
    shim.register_analytics = AsyncMock(return_value={
        "status": "approved",
        "username": "dls_vision_user",
        "password": "secret123",
        "request_id": "req-1",
    })
    shim.set_integration_credentials = MagicMock()
    return shim


def _make_db_record(username="dls_vision_user", password="secret123"):
    record = MagicMock()
    record.nx_username = username
    record.nx_password = password
    return record


async def _run_on_startup(shim: NxWitnessVmsShim, db_record, nx_record):
    """Helper: run shim.on_startup with patched DB and Nx lookups."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(_SAMPLE_MANIFESTS, f)
        manifest_path = f.name

    shim._config = VmsInstanceConfig(
        name=shim._config.name,
        vendor="nx_witness",
        base_url="https://localhost:7001",
        auth=VmsAuthConfig(username="admin", password="pass"),
        analytics_manifest_path=manifest_path,
    )
    shim.find_integration_in_vms = AsyncMock(return_value=nx_record)

    config = _make_config(manifest_path)
    orch = Orchestrator(config)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("plugin.core.db.session.get_session_factory", return_value=lambda: mock_session),
        patch("vms_shim.nxwitness.repository.get_nx_integration", AsyncMock(return_value=db_record)),
        patch("vms_shim.nxwitness.repository.upsert_nx_integration", AsyncMock(return_value=MagicMock())),
    ):
        await shim.on_startup(orch)

    return shim.set_integration_credentials


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_credentials_restored_from_db_on_restart():
    """On restart: DB ✅ + Nx ✅ → set_integration_credentials() called with DB values."""
    nx_record = {"username": "dls_vision_user", "password": "", "request_id": "req-1"}
    db_record = _make_db_record(username="dls_vision_user", password="secret123")
    shim = _make_shim(nx_record=nx_record)

    set_creds = await _run_on_startup(shim, db_record, nx_record)

    set_creds.assert_called_once_with("dls_vision_user", "secret123")


async def test_credentials_not_called_when_password_missing_in_db():
    """DB ✅ + Nx ✅ but no password stored → set_integration_credentials NOT called."""
    nx_record = {"username": "dls_vision_user", "password": "", "request_id": "req-1"}
    db_record = _make_db_record(username="dls_vision_user", password=None)
    shim = _make_shim(nx_record=nx_record)

    set_creds = await _run_on_startup(shim, db_record, nx_record)

    set_creds.assert_not_called()


async def test_credentials_set_on_fresh_registration():
    """DB ❌ + Nx ❌ → fresh registration → set_integration_credentials called with Nx response."""
    shim = _make_shim(nx_record=None)

    set_creds = await _run_on_startup(shim, db_record=None, nx_record=None)

    set_creds.assert_called_once_with("dls_vision_user", "secret123")


async def test_credentials_not_set_on_mismatch_db_missing():
    """DB ❌ + Nx ✅ → error path → set_integration_credentials NOT called."""
    nx_record = {"username": "dls_vision_user", "password": "", "request_id": "req-1"}
    shim = _make_shim(nx_record=nx_record)

    set_creds = await _run_on_startup(shim, db_record=None, nx_record=nx_record)

    set_creds.assert_not_called()

