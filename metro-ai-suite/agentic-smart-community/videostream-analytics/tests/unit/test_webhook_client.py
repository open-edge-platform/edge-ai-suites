"""Tests for WebhookClient with mocked HTTP."""

from unittest.mock import patch, MagicMock

import httpx
import pytest

from shared.config import WebhookConfig
from shared.webhook_client import WebhookClient


@pytest.fixture
def webhook_config():
    return WebhookConfig(
        url="http://localhost:9999/events",
        timeout=5,
        retry_attempts=3,
        retry_delay=0.01,  # Fast retries for tests
    )


@pytest.fixture
def client(webhook_config):
    c = WebhookClient(webhook_config)
    yield c
    c.close()


class TestWebhookClientSuccess:
    def test_send_event_returns_true_on_200(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch.object(client._client, "post", return_value=mock_resp):
            result = client.send_event({"event_type": "test"})
        assert result is True

    def test_send_event_posts_payload_verbatim(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        payload = {
            "source_id": "cam_child",
            "event_type": "motion",
            "start_time": "2026-06-08T10:00:00",
            "duration_seconds": 10.0,
            "clip_path": "/data/cam_child/motion_events/2026-06-08/clip.mp4",
        }
        with patch.object(client._client, "post", return_value=mock_resp) as mock_post:
            client.send_event(payload)
        assert mock_post.call_args.kwargs["json"] == payload


class TestWebhookClientRetry:
    def test_retries_on_server_error(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        with patch.object(client._client, "post", return_value=mock_resp) as mock_post:
            result = client.send_event({"test": True})
        assert result is False
        assert mock_post.call_count == 3  # retry_attempts = 3

    def test_retries_on_network_error(self, client):
        with patch.object(
            client._client, "post", side_effect=httpx.ConnectError("Connection refused")
        ) as mock_post:
            result = client.send_event({"test": True})
        assert result is False
        assert mock_post.call_count == 3

    def test_succeeds_after_partial_failure(self, client):
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.text = "Error"
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        with patch.object(
            client._client, "post", side_effect=[fail_resp, fail_resp, ok_resp]
        ):
            result = client.send_event({"test": True})
        assert result is True
