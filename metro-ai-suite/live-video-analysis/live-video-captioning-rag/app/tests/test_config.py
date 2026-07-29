# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.config."""

import importlib


class TestConfigDefaults:
    """Verify fallback defaults are stable."""

    def test_app_port_default(self, monkeypatch):
        monkeypatch.delenv("APP_PORT", raising=False)
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.APP_PORT == 4172

    def test_top_k_default(self, monkeypatch):
        monkeypatch.delenv("TOP_K", raising=False)
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.TOP_K == 1

    def test_score_threshold_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("SCORE_THRESHOLD", raising=False)
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.SCORE_THRESHOLD == 0.3


class TestConfigFromEnv:
    """Verify env overrides are parsed correctly."""

    def test_app_port_from_env(self, monkeypatch):
        monkeypatch.setenv("APP_PORT", "9000")
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.APP_PORT == 9000

    def test_top_k_from_env(self, monkeypatch):
        monkeypatch.setenv("TOP_K", "5")
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.TOP_K == 5

    def test_score_threshold_from_env(self, monkeypatch):
        monkeypatch.setenv("SCORE_THRESHOLD", "0.85")
        import backend.config as cfg

        importlib.reload(cfg)
        assert cfg.SCORE_THRESHOLD == 0.85
