"""Unit tests for isolated helpers in mqtt_listener to boost coverage without real broker."""
import pytest
from service import mqtt_listener

def test_iso_to_frigate_timestamp_valid():
    ts = mqtt_listener.iso_to_frigate_timestamp("2025-01-02T03:04:05Z")
    assert ts.startswith("17")  # epoch prefix (rough sanity)
    assert "." in ts

def test_iso_to_frigate_timestamp_invalid():
    raw = "not-a-timestamp"
    out = mqtt_listener.iso_to_frigate_timestamp(raw)
    assert out == raw  # falls back unchanged
