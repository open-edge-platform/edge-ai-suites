# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Example prompt: quick MQTT Docker Compose deploy + smoke test

> Quickly build and deploy the wind turbine anomaly detection app with MQTT
> ingestion via Docker Compose, then run a smoke test and report whether
> it's healthy.

Expected agent flow:
1. Resolve app root, check `.env`, run Docker preflight.
2. `make build`
3. `make up_mqtt_ingestion app=wind-turbine-anomaly-detection`
4. `scripts/smoke-check.sh docker`
5. Report real command output and a clear PASS/FAIL summary.
6. Offer `make down` for cleanup.
