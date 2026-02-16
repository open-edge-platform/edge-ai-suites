# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for the configuration module (app/config.py).

Covers:
- Integer environment variable parsing with valid, invalid and missing values
- Default values for METRICS_PORT, LOG_LEVEL, and CORS_ORIGINS
- CORS_ORIGINS comma-separated splitting
"""

import importlib

import pytest


# ---------------------------------------------------------------------------
# _get_int_env helper
# ---------------------------------------------------------------------------

class TestGetIntEnv:
    """Tests for the _get_int_env helper function."""

    def test_returns_default_when_env_var_not_set(self, monkeypatch):
        """_get_int_env returns the default when the env var is absent."""
        monkeypatch.delenv("METRICS_PORT", raising=False)
        from app.config import _get_int_env
        assert _get_int_env("METRICS_PORT", 9090) == 9090

    def test_returns_env_value_when_set(self, monkeypatch):
        """_get_int_env returns the parsed integer when the env var is set."""
        monkeypatch.setenv("METRICS_PORT", "8080")
        from app.config import _get_int_env
        assert _get_int_env("METRICS_PORT", 9090) == 8080

    def test_returns_default_on_invalid_value(self, monkeypatch, capsys):
        """_get_int_env falls back to default and prints an error for non-integer values."""
        monkeypatch.setenv("METRICS_PORT", "not_a_number")
        from app.config import _get_int_env
        result = _get_int_env("METRICS_PORT", 9090)
        assert result == 9090
        captured = capsys.readouterr()
        assert "Invalid value" in captured.err

    def test_handles_empty_string(self, monkeypatch, capsys):
        """_get_int_env treats an empty string as invalid and returns the default."""
        monkeypatch.setenv("METRICS_PORT", "")
        from app.config import _get_int_env
        result = _get_int_env("METRICS_PORT", 9090)
        assert result == 9090
        captured = capsys.readouterr()
        assert "Invalid value" in captured.err

    def test_handles_zero_value(self, monkeypatch):
        """_get_int_env correctly parses '0' as the integer 0."""
        monkeypatch.setenv("MY_VAR", "0")
        from app.config import _get_int_env
        assert _get_int_env("MY_VAR", 42) == 0

    def test_handles_negative_value(self, monkeypatch):
        """_get_int_env correctly parses a negative integer string."""
        monkeypatch.setenv("MY_VAR", "-5")
        from app.config import _get_int_env
        assert _get_int_env("MY_VAR", 42) == -5


# ---------------------------------------------------------------------------
# Module-level configuration variables
# ---------------------------------------------------------------------------

class TestModuleConfig:
    """Tests for module-level config values set at import time."""

    def test_default_metrics_port(self, monkeypatch):
        """METRICS_PORT defaults to 9090 when env var is not set."""
        monkeypatch.delenv("METRICS_PORT", raising=False)
        import app.config as cfg
        reloaded = importlib.reload(cfg)
        assert reloaded.METRICS_PORT == 9090

    def test_custom_metrics_port(self, monkeypatch):
        """METRICS_PORT reflects a custom env var value after reload."""
        monkeypatch.setenv("METRICS_PORT", "7070")
        import app.config as cfg
        reloaded = importlib.reload(cfg)
        assert reloaded.METRICS_PORT == 7070

    def test_default_log_level(self, monkeypatch):
        """LOG_LEVEL defaults to 'INFO' when env var is not set."""
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        import app.config as cfg
        reloaded = importlib.reload(cfg)
        assert reloaded.LOG_LEVEL == "INFO"

    def test_custom_log_level(self, monkeypatch):
        """LOG_LEVEL reflects a custom env var value."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        import app.config as cfg
        reloaded = importlib.reload(cfg)
        assert reloaded.LOG_LEVEL == "DEBUG"

    def test_default_cors_origins(self, monkeypatch):
        """CORS_ORIGINS defaults to ['*'] when env var is not set."""
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        import app.config as cfg
        reloaded = importlib.reload(cfg)
        assert reloaded.CORS_ORIGINS == ["*"]

    def test_single_cors_origin(self, monkeypatch):
        """CORS_ORIGINS correctly parses a single origin."""
        monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
        import app.config as cfg
        reloaded = importlib.reload(cfg)
        assert reloaded.CORS_ORIGINS == ["http://localhost:3000"]

    def test_multiple_cors_origins(self, monkeypatch):
        """CORS_ORIGINS correctly splits comma-separated origins."""
        monkeypatch.setenv("CORS_ORIGINS", "http://a.com,http://b.com,http://c.com")
        import app.config as cfg
        reloaded = importlib.reload(cfg)
        assert reloaded.CORS_ORIGINS == ["http://a.com", "http://b.com", "http://c.com"]
