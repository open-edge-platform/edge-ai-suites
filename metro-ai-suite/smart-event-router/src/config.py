# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os

# Frigate base url
# Get environment variables with defaults (optional)

# Combine safely
FRIGATE_BASE_URL = os.getenv("FRIGATE_BASE_URL")
# VSS Service url
VSS_SUMMARY_URL = os.getenv("VSS_SUMMARY_URL")
VSS_SEARCH_URL = os.getenv("VSS_SEARCH_URL")
no_proxy: str = os.getenv("no_proxy")
MQTT_BROKER = os.getenv("HOST_IP", "mqtt-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1884))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "frigate/events")
REDIS_HOST = os.getenv("HOST_IP", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# Scenescape MQTT Configuration
NVR_SCENESCAPE_ENABLED = os.getenv("NVR_SCENESCAPE", "false").lower() == "true"
SCENESCAPE_MQTT_BROKER = os.getenv("SCENESCAPE_MQTT_BROKER", os.getenv("HOST_IP", "broker"))
SCENESCAPE_MQTT_PORT = int(os.getenv("SCENESCAPE_MQTT_PORT", 1883))
SCENESCAPE_MQTT_TOPIC = os.getenv("SCENESCAPE_MQTT_TOPIC", "scenescape/data/camera/#")

# Scenescape throttling configuration
SCENESCAPE_THROTTLE_INTERVAL = float(os.getenv("SCENESCAPE_THROTTLE_INTERVAL", 2.0))

# Multi-broker (scenescape mode) configuration
BROKERS_CONFIG_PATH = os.getenv("BROKERS_CONFIG_PATH", "resources/broker-config/brokers.yaml")
MAX_CONCURRENT_EVENTS = int(os.getenv("MAX_CONCURRENT_EVENTS", 50))
BROKER_RECONNECT_DELAY = float(os.getenv("BROKER_RECONNECT_DELAY", 5.0))

