# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Example prompt: quick Docker Compose deploy + smoke test

> Quickly build and deploy the weld defect detection app with Docker Compose
> (default variant), then run a smoke test and report whether it's healthy.

Expected agent flow:
1. Resolve app root, check `.env`, run Docker preflight.
2. `make build`
3. `make up`
4. `scripts/smoke-check.sh docker`
5. Report real command output and a clear PASS/FAIL summary.
6. Offer `make down` for cleanup.
