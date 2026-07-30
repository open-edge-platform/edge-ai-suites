<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Golden fixture for `scripts/reconcile-report.sh` self-test only.

# Onboarding Validation Report: Sample App

### Summary

| Field | Value |
|-------|-------|
| Rules Version | 1.4.0 |
| Skill Version | 1.12.0 |
| Date | 2026-07-29 |
| Application | sample-app |
| GitHub URL | https://example.invalid/org/repo/tree/release-2026.1/sample-app |
| Commit | 1111111111111111111111111111111111111111 |
| Deployment method | docker-compose |
| OS | Ubuntu 24.04 |
| CPU | Test CPU |
| RAM | 32 GiB |
| GPU | not found |
| NPU | not found |
| Documentation path followed | 1. README.md -> "Getting Started" |

**Overall UX Score**

```text
████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 4.0 / 10 — Poor
```

| Total Rules | ✅ PASS | 🔴 FAIL (Critical) | 🟠 FAIL (Major) | 🟡 FAIL (Minor) | ⚪ N/A |
|-------------|------|-----------------|-----------------|-----------------|-----|
| 15          | 9    | 1               | 2               | 1               | 2   |

**Overall Result**: FAIL

### Detailed Results

| ID | Rule (short) | Result | Severity | Evidence / Reason |
|----|--------------|--------|----------|-------------------|
| 1.1 | Partial clone used | ✅ PASS | — | sample evidence |
| 1.2 | Clone size ≤ 100 MB | ✅ PASS | — | sample evidence |
| 1.3 | Branch/tag specified | ❌ FAIL | Major | sample evidence |
| 1.4 | Sparse-checkout scoped | ✅ PASS | — | sample evidence |
| 1.5 | Clone time < 2 min | ❌ FAIL | Minor | sample evidence |
| 2.1 | Shared prerequisites page | ✅ PASS | — | sample evidence |
| 2.2 | Max 3 external tools | ❌ FAIL | Critical | sample evidence |
| 2.3 | No host runtimes | ⚪ N/A | — | sample evidence |
| 2.4 | Automated model download | ✅ PASS | — | sample evidence |
| 2.5 | Tool versions specified | ✅ PASS | — | sample evidence |
| 2.6 | App-specific prereqs on page | ✅ PASS | — | sample evidence |
| 2.7 | Exact prerequisite edition | ✅ PASS | — | sample evidence |
| 3.1 | Zero config startup | ❌ FAIL | Major | sample evidence |
| 3.2 | No host-specific values | ⚪ N/A | — | sample evidence |
| 3.3 | Single config file | ✅ PASS | — | sample evidence |
