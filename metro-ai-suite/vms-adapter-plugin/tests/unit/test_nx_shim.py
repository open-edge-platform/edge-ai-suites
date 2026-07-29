# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the Nx Witness single-shim using standard /rest/v4 endpoints."""

from unittest.mock import AsyncMock

import pytest

from plugin.core.config import VmsAuthConfig, VmsInstanceConfig
from vms_shim.nxwitness import shim as nx_module
from vms_shim.nxwitness.shim import NxWitnessVmsShim


@pytest.fixture
def nx_config() -> VmsInstanceConfig:
    return VmsInstanceConfig(
        name="nx-test", vendor="nx_witness",
        base_url="https://localhost:7001",
        auth=VmsAuthConfig(username="admin", password="test", auth_type="digest"),
    )


def test_initial_state(nx_config):
    shim = NxWitnessVmsShim(nx_config)
    assert shim.is_connected() is False


@pytest.mark.asyncio
async def test_get_live_stream_url_includes_onvif_replay(nx_config):
    shim = NxWitnessVmsShim(nx_config)
    url = await shim.get_live_stream_url("nx:device-1")
    assert url == "rtsp://admin:test@localhost:7001/device-1?onvif_replay=true"


@pytest.mark.asyncio
async def test_unsupported_when_disconnected(nx_config):
    shim = NxWitnessVmsShim(nx_config)
    cr = await shim.set_bookmark("nx:cam1", __import__("datetime").datetime.utcnow(), "x")
    assert cr.status == "unsupported"


@pytest.mark.asyncio
async def test_acknowledge_is_unsupported(nx_config):
    """Standard /rest/v4 has no event-acknowledge endpoint."""
    shim = NxWitnessVmsShim(nx_config)
    cr = await shim.acknowledge_event("nx:cam1", "evt1")
    assert cr.status == "unsupported"


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._p = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                "error", request=None, response=self  # type: ignore[arg-type]
            )

    def json(self):
        return self._p


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def get(self, path, params=None):
        self.calls.append(("GET", path, params))
        return _FakeResp(self.payload)


@pytest.mark.asyncio
async def test_discover_cameras_uses_rest_v4_devices(nx_config):
    shim = NxWitnessVmsShim(nx_config)
    fake = _FakeClient([
        {"id": "device-1", "name": "Front Door", "url": "rtsp://nx/front-door",
         "status": "Online", "deviceType": "Camera"},
        {"id": "device-2", "name": "Speaker",
         "status": "Online", "deviceType": "IoModule"},
    ])
    shim._client = fake
    cams = await shim.discover_cameras()
    assert fake.calls == [("GET", "/rest/v4/devices", None)]
    assert len(cams) == 1
    assert cams[0].camera_id == "nx:device-1"


# ── register_analytics tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_analytics_no_manifest_lists_engines(nx_config):
    """Empty manifest falls back to listing Nx engines."""
    shim = NxWitnessVmsShim(nx_config)
    fake = _FakeClient([{"id": "eng-1"}])
    shim._client = fake
    result = await shim.register_analytics({})
    assert result["status"] == "ok"
    assert result["engines"] == [{"id": "eng-1"}]


@pytest.mark.asyncio
async def test_register_analytics_not_connected(nx_config):
    shim = NxWitnessVmsShim(nx_config)
    # _client is None (not connected)
    result = await shim.register_analytics({
        "integrationManifest": {"id": "test"},
        "engineManifest": {"typeLibrary": {}},
    })
    assert result["status"] == "error"
    assert result["reason"] == "not_connected"


class _FullRegistrationClient:
    """Fake client that simulates Phase 1 Nx REST workflow."""

    def __init__(self):
        self.calls: list[tuple] = []

    async def post(self, path, json=None):
        self.calls.append(("POST", path, json))
        if "requests" in path and "approve" not in path:
            return _FakeResp({
                "username": "integration_user",
                "password": "secret123",
                "requestId": "req-abc-123",
            })
        if "approve" in path:
            return _FakeResp({})
        return _FakeResp({})


@pytest.mark.asyncio
async def test_register_analytics_full_phase1_success(nx_config):
    """Full Phase 1: create request + approve → returns approved credentials."""
    shim = NxWitnessVmsShim(nx_config)
    shim._client = _FullRegistrationClient()

    manifests = {
        "integrationManifest": {"id": "test.integration", "name": "Test"},
        "engineManifest": {"typeLibrary": {"objectTypes": []}},
        "deviceAgentManifest": {"supportedTypes": []},
        "pinCode": "9999",
    }
    result = await shim.register_analytics(manifests)

    assert result["status"] == "approved"
    assert result["username"] == "integration_user"
    assert result["password"] == "secret123"
    assert result["request_id"] == "req-abc-123"

    calls = shim._client.calls
    # First call: create integration request
    assert calls[0][1] == "/rest/v4/analytics/integrations/*/requests"
    assert calls[0][2]["pinCode"] == "9999"
    assert calls[0][2]["integrationManifest"]["id"] == "test.integration"
    assert calls[0][2]["isRestOnly"] is True
    # Second call: approve
    assert "approve" in calls[1][1]
    assert calls[1][2]["requestId"] == "req-abc-123"


@pytest.mark.asyncio
async def test_register_analytics_without_device_agent_manifest(nx_config):
    """deviceAgentManifest is optional; should not be sent if absent."""
    shim = NxWitnessVmsShim(nx_config)
    shim._client = _FullRegistrationClient()

    manifests = {
        "integrationManifest": {"id": "test.integration", "name": "Test"},
        "engineManifest": {"typeLibrary": {}},
    }
    result = await shim.register_analytics(manifests)
    assert result["status"] == "approved"

    create_call_payload = shim._client.calls[0][2]
    assert "deviceAgentManifest" not in create_call_payload


class _FailApprovalClient(_FullRegistrationClient):
    """Create succeeds but approve fails."""

    async def post(self, path, json=None):
        self.calls.append(("POST", path, json))
        if "requests" in path and "approve" not in path:
            return _FakeResp({
                "username": "user", "password": "pw", "requestId": "req-1",
            })
        # Approval returns 500
        return _FakeResp({}, status_code=500)


@pytest.mark.asyncio
async def test_register_analytics_approval_failure(nx_config):
    """If approval fails, status is 'registered' not 'approved'."""
    shim = NxWitnessVmsShim(nx_config)
    shim._client = _FailApprovalClient()

    manifests = {
        "integrationManifest": {"id": "test"},
        "engineManifest": {"typeLibrary": {}},
    }
    result = await shim.register_analytics(manifests)
    assert result["status"] == "registered"
    assert result["username"] == "user"
    assert "reason" in result


@pytest.mark.asyncio
async def test_connect_uses_tls_verify_from_config(monkeypatch):
    cfg = VmsInstanceConfig(
        name="nx-test",
        vendor="nx_witness",
        base_url="https://localhost:7001",
        tls_verify=True,
        auth=VmsAuthConfig(username="admin", password="test", auth_type="digest"),
    )
    shim = NxWitnessVmsShim(cfg)
    shim._login = AsyncMock()

    captured: dict = {}

    def _fake_async_client(*args, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(nx_module.httpx, "AsyncClient", _fake_async_client)
    await shim.connect()
    assert captured["verify"] is True


@pytest.mark.asyncio
async def test_integration_client_uses_ca_bundle_when_tls_verify_enabled(monkeypatch):
    cfg = VmsInstanceConfig(
        name="nx-test",
        vendor="nx_witness",
        base_url="https://localhost:7001",
        tls_verify=True,
        tls_ca_bundle="/tmp/nx-ca.pem",
        auth=VmsAuthConfig(username="admin", password="test", auth_type="digest"),
    )
    shim = NxWitnessVmsShim(cfg)
    shim.set_integration_credentials("integration", "secret")

    captured: dict = {}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"token": "tok"}

    class _Client:
        def __init__(self):
            self.headers = {}

        async def post(self, path, json=None):
            return _Resp()

        async def aclose(self):
            return None

    def _fake_async_client(*args, **kwargs):
        captured.update(kwargs)
        return _Client()

    monkeypatch.setattr(nx_module.httpx, "AsyncClient", _fake_async_client)
    ok = await shim._ensure_integration_session()

    assert ok is True
    assert captured["verify"] == "/tmp/nx-ca.pem"
