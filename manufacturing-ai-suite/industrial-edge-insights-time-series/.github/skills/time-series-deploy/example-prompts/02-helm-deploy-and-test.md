# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Example prompt: Helm deploy + functional tests

> Deploy the wind turbine anomaly detection app to my Kubernetes cluster with
> Helm, then run the Helm functional test suite and tell me if anything
> failed.

Expected agent flow:
1. Resolve app root, check `.env`, run Kubernetes/Helm preflight.
2. `make gen_helm_charts app=wind-turbine-anomaly-detection`
3. Confirm `helm/values.yaml` required fields are populated (ask user if not).
4. `helm install ts-wind-turbine-anomaly ./helm -n ts-sample-app --create-namespace`
5. `.github/skills/time-series-deploy/scripts/smoke-check.sh helm ts-sample-app`
6. `.github/skills/time-series-deploy/scripts/run-functional-tests.sh helm default`
7. Summarize pytest PASS/FAIL counts; offer `helm uninstall` for cleanup.
