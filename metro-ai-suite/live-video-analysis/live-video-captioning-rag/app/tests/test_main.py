# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for app bootstrap and route wiring in main.py."""

from types import ModuleType
import runpy
import sys

from fastapi import APIRouter
from starlette.requests import Request


def _make_request(path="/", headers=None, host="testserver"):
    headers = headers or {}
    raw_headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()]
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("latin-1"),
        "query_string": b"",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "server": (host, 80),
    }
    return Request(scope)


class TestRootEndpoint:
    """GET / endpoint should serve frontend content."""

    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_serves_html(self, client):
        resp = client.get("/")
        assert "html" in resp.headers.get("content-type", "").lower()

    def test_root_blocks_top_level_navigation_in_embedded_mode(self, embedded_client):
        resp = embedded_client.get(
            "/",
            headers={
                "accept": "text/html",
                "sec-fetch-mode": "navigate",
                "sec-fetch-dest": "document",
            },
        )
        assert resp.status_code == 403

    def test_root_allows_iframe_navigation_in_embedded_mode(self, embedded_client):
        resp = embedded_client.get(
            "/",
            headers={
                "accept": "text/html",
                "sec-fetch-mode": "navigate",
                "sec-fetch-dest": "iframe",
            },
        )
        assert resp.status_code == 200

    def test_root_allows_dashboard_referrer_in_embedded_mode(self, embedded_client):
        resp = embedded_client.get(
            "/",
            headers={
                "accept": "text/html",
                "sec-fetch-mode": "navigate",
                "referer": "http://testserver:4173/",
            },
        )
        assert resp.status_code == 200

    def test_root_navigation_allowed_in_detached_mode(self, client):
        resp = client.get(
            "/",
            headers={
                "accept": "text/html",
                "sec-fetch-mode": "navigate",
                "sec-fetch-dest": "document",
            },
        )
        assert resp.status_code == 200

    def test_root_allows_api_path_in_embedded_mode(self, embedded_client):
        resp = embedded_client.get("/api/health")
        assert resp.status_code == 200

    def test_root_allows_non_navigation_request_in_embedded_mode(self, embedded_client):
        resp = embedded_client.get(
            "/",
            headers={
                "accept": "application/json",
                "sec-fetch-mode": "cors",
            },
        )
        assert resp.status_code == 200

    def test_root_blocks_navigation_with_host_mismatch_referrer(self, embedded_client):
        resp = embedded_client.get(
            "/",
            headers={
                "accept": "text/html",
                "sec-fetch-mode": "navigate",
                "referer": "http://other-host:4173/",
            },
        )
        assert resp.status_code == 403

    def test_root_blocks_when_referrer_parse_fails(self, embedded_client, monkeypatch):
        import main

        def _raise_value_error(_value):
            raise ValueError("bad referrer")

        monkeypatch.setattr(main, "urlparse", _raise_value_error)
        resp = embedded_client.get(
            "/",
            headers={
                "accept": "text/html",
                "sec-fetch-mode": "navigate",
                "referer": "http://testserver:4173/",
            },
        )
        assert resp.status_code == 403


class TestReferrerSchemeFallback:
    """Referrer checks without explicit ports should use scheme defaults."""

    def test_https_referrer_without_port_not_allowed_for_non_443_dashboard(self, monkeypatch):
        import main

        monkeypatch.setattr(main, "DASHBOARD_PORT", 4173)
        req = _make_request(headers={"referer": "https://testserver/path"})
        assert main._is_from_dashboard_referrer(req) is False

    def test_http_referrer_without_port_not_allowed_for_non_80_dashboard(self, monkeypatch):
        import main

        monkeypatch.setattr(main, "DASHBOARD_PORT", 4173)
        req = _make_request(headers={"referer": "http://testserver/path"})
        assert main._is_from_dashboard_referrer(req) is False

    def test_unknown_scheme_without_port_is_not_allowed(self):
        import main

        req = _make_request(headers={"referer": "ftp://testserver/path"})
        assert main._is_from_dashboard_referrer(req) is False


class TestRouteRegistration:
    """All public API routers are mounted."""

    def test_health_route_registered(self, client):
        """The health check route is registered and returns 200."""
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_model_route_registered(self, client):
        """The model info route is registered and returns 200."""
        resp = client.get("/api/model")
        assert resp.status_code == 200

    def test_embedding_route_registered(self, client):
        """The embedding route is registered and returns 200."""
        resp = client.post("/api/embeddings", json={"image_data": "abc", "metadata": {"result": "x"}})
        assert resp.status_code == 200

    def test_chat_route_registered(self, client):
        """The chat route is registered and returns 200."""
        resp = client.post("/api/chat", json={"input": "hello"})
        assert resp.status_code == 200


def test_main_dunder_invokes_uvicorn(monkeypatch, tmp_path):
    """Running main as __main__ should call uvicorn.run with configured host/port."""
    ui_dir = tmp_path / "ui"
    ui_dir.mkdir()
    (ui_dir / "index.html").write_text("<html><body>ok</body></html>")

    cfg_mod = ModuleType("backend.config")
    cfg_mod.APP_PORT = 4999
    cfg_mod.DASHBOARD_PORT = 4173
    cfg_mod.RAG_CHATBOT_MODE = "detached"
    cfg_mod.UI_DIR = ui_dir

    routes_mod = ModuleType("backend.routes")
    routes_mod.chat_router = APIRouter()
    routes_mod.model_router = APIRouter()
    routes_mod.embedding_router = APIRouter()
    routes_mod.health_router = APIRouter()

    uvicorn_mod = ModuleType("uvicorn")
    calls = {}

    def _fake_run(*args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs

    uvicorn_mod.run = _fake_run

    monkeypatch.setitem(sys.modules, "backend.config", cfg_mod)
    monkeypatch.setitem(sys.modules, "backend.routes", routes_mod)
    monkeypatch.setitem(sys.modules, "uvicorn", uvicorn_mod)
    sys.modules.pop("main", None)

    runpy.run_module("main", run_name="__main__")

    assert calls["args"] == ("main:app",)
    assert calls["kwargs"]["host"] == "0.0.0.0"
    assert calls["kwargs"]["port"] == 4999
    assert calls["kwargs"]["reload"] is True
