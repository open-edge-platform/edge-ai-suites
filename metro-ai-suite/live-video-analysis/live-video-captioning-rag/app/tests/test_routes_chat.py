# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.routes.chat."""

from unittest.mock import patch


class TestChatEndpoint:
    """POST /api/chat endpoint."""

    def test_rejects_empty_input(self, client):
        resp = client.post("/api/chat", json={"input": ""})
        assert resp.status_code == 422
        assert "required" in resp.json()["detail"].lower()

    def test_returns_event_stream(self, client):
        def _fake_chain():
            return object()

        async def _fake_stream(_chain=None, _query=""):
            yield "data: first token\\n\\n"
            yield "event: frame\\n"
            yield "data: []\\n\\n"

        with patch("backend.routes.chat.build_chain", _fake_chain), patch(
            "backend.routes.chat.process_query", _fake_stream
        ):
            resp = client.post("/api/chat", json={"input": "What is happening?"})

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert "data: first token" in resp.text
        assert "event: frame" in resp.text
