# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Example prompt: Helm deploy + functional tests

> Deploy the multimodal weld defect detection sample app to my Kubernetes
> cluster with Helm, then run the Helm functional test suite and tell me if
> anything failed.

Expected agent flow:
1. Resolve app root, check `.env`, run Kubernetes/Helm preflight.
2. `make gen_helm_charts`
3. Confirm `helm/values.yaml` required fields are populated (ask user if not).
4. `helm install multimodal-weld-defect-detection ./helm -n multimodal-sample-app --create-namespace`
5. `.github/skills/multimodal-deploy/scripts/smoke-check.sh helm multimodal-sample-app`
6. `.github/skills/multimodal-deploy/scripts/run-functional-tests.sh helm cpu`
7. Summarize pytest PASS/FAIL counts; offer `helm uninstall` for cleanup.
