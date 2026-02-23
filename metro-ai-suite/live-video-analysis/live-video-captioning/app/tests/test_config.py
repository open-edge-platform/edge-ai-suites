# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.config, environment-driven configuration values."""

import importlib


class TestConfigDefaults:
    """Verify that config values fall back to sensible defaults."""

    def test_app_port_default(self, monkeypatch):
        """APP_PORT defaults to 4173 when DASHBOARD_PORT is not set."""
        monkeypatch.delenv("DASHBOARD_PORT", raising=False)
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.APP_PORT == 4173

    def test_app_port_from_env(self, monkeypatch):
        """APP_PORT reads from the DASHBOARD_PORT environment variable."""
        monkeypatch.setenv("DASHBOARD_PORT", "9999")
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.APP_PORT == 9999

    def test_peer_id_default(self, monkeypatch):
        """PEER_ID defaults to 'genai_pipeline'."""
        monkeypatch.delenv("WEBRTC_PEER_ID", raising=False)
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.PEER_ID == "genai_pipeline"

    def test_signaling_url_default(self, monkeypatch):
        """SIGNALING_URL defaults to http://localhost:8889."""
        monkeypatch.delenv("SIGNALING_URL", raising=False)
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.SIGNALING_URL == "http://localhost:8889"

    def test_webrtc_bitrate_default(self, monkeypatch):
        """WEBRTC_BITRATE defaults to 2048."""
        monkeypatch.delenv("WEBRTC_BITRATE", raising=False)
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.WEBRTC_BITRATE == 2048

    def test_webrtc_bitrate_from_env(self, monkeypatch):
        """WEBRTC_BITRATE is read from env as an integer."""
        monkeypatch.setenv("WEBRTC_BITRATE", "5000")
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.WEBRTC_BITRATE == 5000


class TestAlertModeFlag:
    """ALERT_MODE boolean parsing from environment."""

    def test_alert_mode_false_by_default(self, monkeypatch):
        """ALERT_MODE is False when not set."""
        monkeypatch.delenv("ALERT_MODE", raising=False)
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.ALERT_MODE is False

    def test_alert_mode_true_values(self, monkeypatch):
        """ALERT_MODE parses 'true', '1', and 'yes' as True."""
        import backend.config as cfg

        for val in ("true", "True", "TRUE", "1", "yes", "Yes"):
            monkeypatch.setenv("ALERT_MODE", val)
            importlib.reload(cfg)
            assert cfg.ALERT_MODE is True, f"Expected True for ALERT_MODE={val}"

    def test_alert_mode_false_values(self, monkeypatch):
        """ALERT_MODE parses other strings as False."""
        import backend.config as cfg

        for val in ("false", "0", "no", "random"):
            monkeypatch.setenv("ALERT_MODE", val)
            importlib.reload(cfg)
            assert cfg.ALERT_MODE is False, f"Expected False for ALERT_MODE={val}"


class TestDetectionPipelineFlag:
    """ENABLE_DETECTION_PIPELINE boolean parsing."""

    def test_detection_pipeline_disabled_by_default(self, monkeypatch):
        """ENABLE_DETECTION_PIPELINE defaults to False."""
        monkeypatch.delenv("ENABLE_DETECTION_PIPELINE", raising=False)
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.ENABLE_DETECTION_PIPELINE is False

    def test_detection_pipeline_enabled(self, monkeypatch):
        """ENABLE_DETECTION_PIPELINE is True when set to 'true'."""
        monkeypatch.setenv("ENABLE_DETECTION_PIPELINE", "true")
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.ENABLE_DETECTION_PIPELINE is True


class TestMQTTConfig:
    """MQTT configuration defaults."""

    def test_mqtt_broker_host_default(self, monkeypatch):
        """MQTT_BROKER_HOST defaults to 'mqtt-broker'."""
        monkeypatch.delenv("MQTT_BROKER_HOST", raising=False)
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.MQTT_BROKER_HOST == "mqtt-broker"

    def test_mqtt_broker_port_default(self, monkeypatch):
        """MQTT_BROKER_PORT defaults to 1883."""
        monkeypatch.delenv("MQTT_BROKER_PORT", raising=False)
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.MQTT_BROKER_PORT == 1883

    def test_mqtt_topic_prefix_default(self, monkeypatch):
        """MQTT_TOPIC_PREFIX defaults to 'live-video-captioning'."""
        monkeypatch.delenv("MQTT_TOPIC_PREFIX", raising=False)
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.MQTT_TOPIC_PREFIX == "live-video-captioning"


class TestDirectoryPaths:
    """Model and UI directory path construction."""

    def test_models_dir_from_env(self, monkeypatch, tmp_path):
        """MODELS_DIR uses the MODELS_DIR environment variable when set."""
        custom = str(tmp_path / "custom_models")
        monkeypatch.setenv("MODELS_DIR", custom)
        import backend.config as cfg

        importlib.reload(cfg)
        assert str(cfg.MODELS_DIR) == custom

    def test_detection_models_dir_from_env(self, monkeypatch, tmp_path):
        """DETECTION_MODELS_DIR uses the DETECTION_MODELS_DIR env var when set."""
        custom = str(tmp_path / "custom_det")
        monkeypatch.setenv("DETECTION_MODELS_DIR", custom)
        import backend.config as cfg

        importlib.reload(cfg)
        assert str(cfg.DETECTION_MODELS_DIR) == custom

    def test_pipeline_server_url_default(self, monkeypatch):
        """PIPELINE_SERVER_URL defaults to the DL Streamer service."""
        monkeypatch.delenv("PIPELINE_SERVER_URL", raising=False)
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.PIPELINE_SERVER_URL == "http://dlstreamer-pipeline-server:8080"
