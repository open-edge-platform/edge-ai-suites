<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Golden fixture for `scripts/self-test.sh` only. Generated with
`scripts/reconcile-report.sh --emit-skeleton` and filled in with synthetic verdicts, so it
reconciles cleanly. It describes no real application; regenerate it whenever the rules file or
the report format contract changes.

# Onboarding Validation Report: Sample App

### Summary

| Field | Value |
|-------|-------|
| Rules Version | 1.4.0 |
| Skill Version | 1.13.0 |
| AI agent | sample-harness (fixture) |
| Model | sample-model (fixture) |
| Date | 2026-07-31 |
| Application | sample-app |
| GitHub URL | https://example.invalid/org/repo/tree/release-2026.1/sample-app |
| Commit | 1111111111111111111111111111111111111111 |
| Deployment method | docker-compose |
| OS | Ubuntu 24.04 |
| CPU | Sample CPU |
| RAM | 32 GiB |
| GPU | not found |
| NPU | not found |
| Documentation path followed | 1. README.md -> "Getting Started" |

**Overall UX Score**

```text
████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 4.0 / 10 — Poor
```

| Total Rules | ✅ PASS | 🔴 FAIL (Critical) | 🟠 FAIL (Major) | 🟡 FAIL (Minor) | ⚪ N/A |
|-------------|------|-----------------|-----------------|-----------------|-----|
| 76 | 54 | 1 | 10 | 6 | 5 |

**Overall Result**: FAIL

### User Experience Summary

**Measured UX Facts**

| # | Metric | Value | Target | Source |
|---|--------|-------|--------|--------|
| 1 | Clone size | | ≤ 100 MB | rule 1.2 |
| 2 | Clone time | | < 2 min | rule 1.5 |
| 3 | Get-started steps | | ≤ 4 | rule 5.1 |
| 4 | Start commands | | 1 | rule 4.2 |
| 5 | App start (deploy) | | < 5 min | rule 4.1 |
| 6 | One-time model prep | | one-time | rule 4.4 |
| 7 | Time-to-first-result | | n/a | rule 7.6 |
| 8 | Image size | | ≤ 30 GB | rule 9.1 |
| 9 | Peak RAM | | ≤ 80% of min | rule 9.2 |
| 10 | External tools | | ≤ 3 | rule 2.2 |
| 11 | UI ready | | ≤ 60 s | rule 7.2 |
| 12 | Minimum skill level | | B | rule 11.6 |

**UX Dimension Scores**

| Dim | Name | Rating (1–10) | Band | Rule basis (non-N/A) → points/max | Notes |
|-----|------|---------------|------|-----------------------------------|-------|
| D1 | Time-to-Deploy | | | | |
| D2 | Setup Effort & Steps | | | | |
| D3 | Prerequisites & Footprint | | | | |
| D4 | Documentation & Skill | | | | |
| D5 | Reliability & Reproducibility | | | | |
| D6 | Cleanup, Security & Observability | | | | |
| D7 | UI & Interaction | | | | |

### Detailed Results

| ID | Rule (short) | Result | Severity | Evidence / Reason |
|----|--------------|--------|----------|-------------------|
| 1.1 | Partial clone used | ✅ PASS | — | verified in the process log (sample) |
| 1.2 | Clone size ≤ 100 MB | ✅ PASS | — | verified in the process log (sample) |
| 1.3 | Branch/tag specified | ✅ PASS | — | verified in the process log (sample) |
| 1.4 | Sparse-checkout scoped | ✅ PASS | — | verified in the process log (sample) |
| 1.5 | Clone time < 2 min | ✅ PASS | — | verified in the process log (sample) |
| 2.1 | Shared prerequisites page | ✅ PASS | — | verified in the process log (sample) |
| 2.2 | Max 3 external tools | ❌ FAIL | Major | documented step missing (sample) |
| 2.3 | No host runtimes | ✅ PASS | — | verified in the process log (sample) |
| 2.4 | Automated model download | ✅ PASS | — | verified in the process log (sample) |
| 2.5 | Tool versions specified | ✅ PASS | — | verified in the process log (sample) |
| 2.6 | App-specific prereqs on page | ❌ FAIL | Minor | cosmetic gap (sample) |
| 2.7 | Exact prerequisite edition | ✅ PASS | — | verified in the process log (sample) |
| 3.1 | Zero config startup | ⚪ N/A | — | not applicable to this deployment method (sample) |
| 3.2 | No host-specific values | ❌ FAIL | Major | documented step missing (sample) |
| 3.3 | Single config file | ✅ PASS | — | verified in the process log (sample) |
| 3.4 | No source code edits | ✅ PASS | — | verified in the process log (sample) |
| 3.5 | Default URLs and ports | ✅ PASS | — | verified in the process log (sample) |
| 3.6 | Auto device selection | ✅ PASS | — | verified in the process log (sample) |
| 3.7 | No token for default model | ✅ PASS | — | verified in the process log (sample) |
| 4.1 | Full deploy < 5 min | ✅ PASS | — | verified in the process log (sample) |
| 4.2 | Single start command | ❌ FAIL | Major | documented step missing (sample) |
| 4.3 | Auto-healthy containers | ❌ FAIL | Minor | cosmetic gap (sample) |
| 4.4 | Auto model provisioning | ✅ PASS | — | verified in the process log (sample) |
| 4.5 | Deployment method documented | ✅ PASS | — | verified in the process log (sample) |
| 5.1 | 3-step pattern | ✅ PASS | — | verified in the process log (sample) |
| 5.2 | Headless verification | ⚪ N/A | — | not applicable to this deployment method (sample) |
| 5.3 | No placeholder edits | ✅ PASS | — | verified in the process log (sample) |
| 5.4 | No conditional branches | ❌ FAIL | Major | documented step missing (sample) |
| 5.5 | Single page deployment | ✅ PASS | — | verified in the process log (sample) |
| 6.1 | No external websites | ✅ PASS | — | verified in the process log (sample) |
| 6.2 | Single image registry | ✅ PASS | — | verified in the process log (sample) |
| 6.3 | No third-party accounts | ✅ PASS | — | verified in the process log (sample) |
| 6.4 | Proxy instructions inline | ❌ FAIL | Minor | cosmetic gap (sample) |
| 7.1 | Clear verification step | ✅ PASS | — | verified in the process log (sample) |
| 7.2 | UI ready in 60s | ❌ FAIL | Major | documented step missing (sample) |
| 7.3 | Health-check per service | ✅ PASS | — | verified in the process log (sample) |
| 7.4 | Actionable error messages | ✅ PASS | — | verified in the process log (sample) |
| 7.5 | All services healthy | ✅ PASS | — | verified in the process log (sample) |
| 7.6 | Functional output verified | ⚪ N/A | — | not applicable to this deployment method (sample) |
| 8.1 | Single teardown command | ✅ PASS | — | verified in the process log (sample) |
| 8.2 | No orphan resources | ✅ PASS | — | verified in the process log (sample) |
| 8.3 | Teardown documented | ❌ FAIL | Major | documented step missing (sample) |
| 9.1 | Images ≤ 30 GB | ✅ PASS | — | verified in the process log (sample) |
| 9.2 | RAM ≤ 80% of minimum | ❌ FAIL | Minor | cosmetic gap (sample) |
| 9.3 | Resource usage documented | ✅ PASS | — | verified in the process log (sample) |
| 10.1 | First-attempt success | ❌ FAIL | Critical | deployment failed on the first attempt (sample) |
| 10.2 | Deterministic result | ✅ PASS | — | verified in the process log (sample) |
| 10.3 | Pinned image tags | ✅ PASS | — | verified in the process log (sample) |
| 10.4 | Offline after setup | ❌ FAIL | Major | documented step missing (sample) |
| 11.1 | Get-started discoverable | ✅ PASS | — | verified in the process log (sample) |
| 11.2 | Architecture overview | ✅ PASS | — | verified in the process log (sample) |
| 11.3 | Performance expectations | ⚪ N/A | — | not applicable to this deployment method (sample) |
| 11.4 | No internal references | ✅ PASS | — | verified in the process log (sample) |
| 11.5 | No assumed expertise | ✅ PASS | — | verified in the process log (sample) |
| 11.6 | Skill level reported | ❌ FAIL | Minor | cosmetic gap (sample) |
| 11.7 | Quick-start visibility | ❌ FAIL | Major | documented step missing (sample) |
| 11.8 | Documentation path recorded | ✅ PASS | — | verified in the process log (sample) |
| 12.1 | Sample input included | ✅ PASS | — | verified in the process log (sample) |
| 12.2 | Simulated live input | ✅ PASS | — | verified in the process log (sample) |
| 12.3 | Sample data ≤ 500 MB | ✅ PASS | — | verified in the process log (sample) |
| 13.1 | No default passwords | ✅ PASS | — | verified in the process log (sample) |
| 13.2 | Credential docs | ✅ PASS | — | verified in the process log (sample) |
| 13.3 | Non-root containers | ❌ FAIL | Major | documented step missing (sample) |
| 13.4 | Minimal port exposure | ✅ PASS | — | verified in the process log (sample) |
| 14.1 | Structured logs to stdout | ⚪ N/A | — | not applicable to this deployment method (sample) |
| 14.2 | Ready message logged | ❌ FAIL | Minor | cosmetic gap (sample) |
| 14.3 | No secrets in logs | ✅ PASS | — | verified in the process log (sample) |
| 15.1 | Optional service failure | ✅ PASS | — | verified in the process log (sample) |
| 15.2 | Device fallback | ✅ PASS | — | verified in the process log (sample) |
| 15.3 | Input retry | ❌ FAIL | Major | documented step missing (sample) |
| 15.4 | Specific error causes | ✅ PASS | — | verified in the process log (sample) |
| 16.1 | Functional in browsers | ✅ PASS | — | verified in the process log (sample) |
| 16.2 | Loading indicator | ✅ PASS | — | verified in the process log (sample) |
| 16.3 | Self-explanatory UI | ✅ PASS | — | verified in the process log (sample) |
| 16.4 | Version and status shown | ✅ PASS | — | verified in the process log (sample) |
| 16.5 | Built-in local input | ✅ PASS | — | verified in the process log (sample) |

### Critical Issues

- Rule 10.1 — deployment failed on the first attempt (synthetic).

### Recommendations

- Critical: fix rule 10.1. Major/Minor: see the FAIL rows above (synthetic).

### Execution Notes

None. This file is synthetic fixture data.
