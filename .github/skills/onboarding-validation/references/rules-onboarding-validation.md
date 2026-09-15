<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AI Agent Validation Rules for Edge AI Suite Applications

| Field | Value |
|-------|-------|
| Version | 1.4.0 |
| Date | 2026-07-21 |
| Status | Active |

These rules define the expected behavior of an application from the customer perspective.
This file is normative for every run of this skill.
An AI agent must use these rules to validate the get-started experience.

Written in ASD-STE100 Simplified Technical English.

> **Versioning policy**: This document follows semantic versioning. The agent MUST include the rules version in every report. When rules change, previous reports remain valid against the version they were evaluated with.

---

## 1. Repository Cloning

| ID | Short | Rule |
|----|-------|------|
| 1.1 | Partial clone used | The clone command MUST use partial cloning (`--filter=blob:none --sparse`) to prevent unnecessary network load. |
| 1.2 | Clone size ≤ 100 MB | The total data downloaded during clone MUST NOT exceed 100 MB for a single application. |
| 1.3 | Branch/tag specified | The clone instruction MUST specify the exact branch or tag. The user MUST NOT need to find the correct version. |
| 1.4 | Sparse-checkout scoped | The sparse-checkout path MUST include only the necessary suite folder. The user MUST NOT download unrelated suites. |
| 1.5 | Clone time < 2 min | The clone step MUST complete in less than 2 minutes on a 50 Mbps connection. |

## 2. Prerequisites and Dependencies

| ID | Short | Rule |
|----|-------|------|
| 2.1 | Shared prerequisites page | Common platform prerequisites (e.g., Docker, Docker Compose, GPU drivers) MUST be documented in a single shared page. Each application MUST link to that page — not duplicate the instructions. |
| 2.2 | Max 3 external tools | The application MUST NOT require more than 3 external tools (e.g., Docker, Docker Compose, git). |
| 2.3 | No host runtimes | The documentation MUST NOT require the user to install language runtimes (Python, Node.js) on the host unless the application does not use containers. |
| 2.4 | Automated model download | All model downloads MUST be automated by a script or a container service. The download MAY be a separate one-time preparation step (not embedded in deployment) but MUST be triggered by a single documented command. The user MUST NOT manually download files from external websites. |
| 2.5 | Tool versions specified | The documentation MUST specify exact versions for all required tools. |
| 2.6 | App-specific prereqs on page | If the application has prerequisites beyond the shared platform page, those MUST be listed on the application's own get-started page. The user MUST NOT need to discover them elsewhere. |
| 2.7 | Exact prerequisite edition | The documentation MUST name the exact edition and install path of each prerequisite for the target OS (e.g., Docker Engine on Linux — not Docker Desktop). Required post-install steps (e.g., adding the user to the `docker` group, restarting the session) MUST be documented inline. |

## 3. Configuration

| ID | Short | Rule |
|----|-------|------|
| 3.1 | Zero config startup | The application MUST NOT require the user to manually edit configuration files or provide input values to start. Automated zero-input scripts (e.g., detecting HOST_IP) are permitted as documented steps. All parameters MUST have working defaults. |
| 3.2 | No host-specific values | The user MUST NOT need to provide host-specific values (e.g., IP address, hostname) to run the application locally. The application MUST auto-detect or default to `localhost`. |
| 3.3 | Single config file | If the user wants to customize behavior, all options MUST be in a single file (`.env` for Docker, `values.yaml` for Helm) with descriptive comments. |
| 3.4 | No source code edits | The documentation MUST NOT require the user to open or edit source code files. |
| 3.5 | Default URLs and ports | All URLs and ports MUST have default values. The user MUST NOT need to discover service endpoints. |
| 3.6 | Auto device selection | The application MUST select the inference device automatically in this order: GPU → NPU → CPU. If a higher-priority device is available, the application MUST use it. The user MUST NOT need to set the device manually for the default path. |
| 3.7 | No token for default model | The default AI model MUST NOT require authentication tokens, account registration, or license acceptance. If such models are supported, they MUST be an optional configuration — not the default. |

## 4. Deployment Time

| ID | Short | Rule |
|----|-------|------|
| 4.1 | Full deploy < 5 min | The full deployment (image pull + container start + model load) MUST complete in less than 5 minutes on a system that meets the minimum requirements. |
| 4.2 | Single start command | All services MUST start with a single `docker compose up`, `helm install`, or `docker run` command. For single-container applications using the `docker` deployment method, a documented thin wrapper (e.g., a `just` recipe that delegates to `docker run` with fixed arguments) is acceptable. Generic wrapper scripts (e.g., `make run`, `./start.sh`) that hide the underlying command are a FAIL (Major) even if they function correctly. Multiple commands (e.g., `make build && make up`) are also Major. |
| 4.3 | Auto-healthy containers | All containers MUST reach a healthy state without manual intervention. |
| 4.4 | Auto model provisioning | If model download is necessary, it MUST be triggered by a single documented command. It MAY run separately from the main deployment and MUST be documented as a one-time setup step. The deployment time threshold (rule 4.1) applies to the application start command — not to model preparation. |
| 4.5 | Deployment method documented | The documentation MUST include deployment instructions for the specified method (Docker Compose, Kubernetes/Helm, or Docker run). If no such instructions exist, this is a Critical FAIL. |

## 5. Number of Steps

| ID | Short | Rule |
|----|-------|------|
| 5.1 | 3-step pattern | The get-started path MUST follow this pattern: (1) clone the repository, (2) start the application (`docker compose up` or `helm install`), (3) verify the result (open the UI, or check the documented output). If the application requires model preparation, one additional automated step (a single command) is permitted between steps 1 and 2 — making the maximum 4 steps. No other manual steps are allowed. |
| 5.2 | Headless verification | If the application does not provide a GUI, the documentation MUST specify a single command to verify the result (e.g., `curl`, `docker compose logs | grep`). This counts as step 3, not an additional step. |
| 5.3 | No placeholder edits | Copy-paste commands MUST work without modification. The user MUST NOT need to replace placeholders to get the application running. |
| 5.4 | No conditional branches | The documentation MUST NOT include conditional branches (e.g., "if X, do Y; otherwise do Z") in the primary get-started path. Optional features MUST be in separate guides. |
| 5.5 | Single page deployment | The user MUST be able to complete the entire deployment on a single documentation page. The get-started guide MUST NOT require switching to other pages for mandatory steps. |

## 6. Network and External Links

| ID | Short | Rule |
|----|-------|------|
| 6.1 | No external websites | The user MUST NOT need to visit external websites to complete the application deployment. The only allowed external reference is the shared platform prerequisites page (see rule 2.1), which the user completes once for all applications. |
| 6.2 | Single image registry | All required container images MUST be available from a single registry (e.g., Docker Hub). |
| 6.3 | No third-party accounts | The default get-started path MUST NOT require the user to create accounts on third-party services. If an optional feature requires an external account (e.g., model hub token for gated models), it MUST be documented separately and MUST NOT block the basic deployment. |
| 6.4 | Proxy instructions inline | If a proxy configuration is necessary, the documentation MUST give exact instructions in the same page. |

## 7. Verification and Feedback

| ID | Short | Rule |
|----|-------|------|
| 7.1 | Clear verification step | The documentation MUST include a clear verification step (e.g., "Open the dashboard at `http://localhost:4173`"). |
| 7.2 | UI ready in 60s | The application MUST show a functional UI within 60 seconds after all containers report healthy status. |
| 7.3 | Health-check per service | The application MUST provide a health-check endpoint or a container health status for each service. |
| 7.4 | Actionable error messages | Error messages MUST be clear and actionable. The user MUST NOT need to read source code to troubleshoot. |
| 7.5 | All services healthy | Container status MUST show all services as running or healthy when deployment is correct. For docker-compose: `docker compose ps`; for docker (single-container): `docker ps --filter name=<container>`. |
| 7.6 | Functional output verified | The agent MUST confirm the application produces its expected functional output (e.g., captions appear on video, objects are detected, data is processed). Healthy containers and a loading UI alone do NOT constitute a passing result. |

## 8. Cleanup and Teardown

| ID | Short | Rule |
|----|-------|------|
| 8.1 | Single teardown command | A single command (`docker compose down`, `helm uninstall`, or `docker stop <name> && docker rm <name>`) MUST stop and remove all resources. |
| 8.2 | No orphan resources | The teardown MUST NOT leave orphan volumes, networks, or processes on the host by default. If persistent storage is supported (e.g., `keepPvc` in Helm), it MUST be disabled by default. |
| 8.3 | Teardown documented | The documentation MUST include the teardown command. |

## 9. Resource Consumption

| ID | Short | Rule |
|----|-------|------|
| 9.1 | Images ≤ 30 GB | The total disk space for all container images MUST NOT exceed 30 GB. |
| 9.2 | RAM ≤ 80% of minimum | The application MUST NOT consume more than 80% of the minimum required RAM during normal operation. |
| 9.3 | Resource usage documented | The documentation MUST state the expected disk, RAM, and GPU usage. |

## 10. Reproducibility

| ID | Short | Rule |
|----|-------|------|
| 10.1 | First-attempt success | An AI agent or a new user MUST be able to deploy the application successfully on the first attempt if the system meets the stated requirements. |
| 10.2 | Deterministic result | The get-started guide MUST produce the same result on every run. No step MUST depend on external state that changes over time. |
| 10.3 | Pinned image tags | All container image tags MUST be pinned to a specific version on release branches. The `latest` tag is allowed only on the `main` branch. |
| 10.4 | Offline after setup | The application MUST NOT require internet access after the initial setup (images pulled, models downloaded). |

## 11. Documentation Quality

| ID | Short | Rule |
|----|-------|------|
| 11.1 | Get-started discoverable | The application's root `README.md` MUST contain a clearly labeled section whose purpose is to guide a new user through installation and first run. Common headings include "Get Started", "Getting Started", "Quick Start", "Quickstart", "Installation", "Setup", "Deploy", "Deployment", "Deployment Options", or similar — the exact wording may vary, but the intent must be unambiguous. The agent MUST select the **first such section encountered when reading from the top** of the README. The user MUST NOT search the directory tree to find deployment instructions. |
| 11.2 | Architecture overview | The get-started guide MUST include an architecture diagram or a service list so the user understands what will be deployed. |
| 11.3 | Performance expectations | The documentation MUST state the expected end-to-end latency or throughput for the default configuration so the user can verify correct operation. |
| 11.4 | No internal references | The documentation MUST NOT reference internal Intel infrastructure, private registries, or VPN-only resources in the public get-started path. |
| 11.5 | No assumed expertise | The get-started instructions MUST be understandable by a user who knows basic terminal usage and Docker commands. The documentation MUST NOT assume knowledge of networking, Kubernetes internals, or ML frameworks without explanation. |
| 11.6 | Skill level reported | The agent MUST evaluate and report the minimum skill level required to complete the deployment: (A) non-technical user, (B) developer familiar with containers, (C) experienced IT/DevOps professional. The target for a get-started guide is level B. |
| 11.7 | Quick-start visibility | If the README contains a simplified quick-start path (e.g., a "Quick Start" or "Quick Start Guide" section) in addition to a full get-started guide, the quick-start MUST be linked or visible within the first screenful (~40 lines) of the README. If a quick-start exists but is buried below the fold, report it as a documentation UX finding. |
| 11.8 | Documentation path recorded | The agent MUST record in the report Summary the exact section heading(s) and document path(s) it followed for installation. If multiple documentation pages were required, each page and section MUST be listed in order. This shows the complexity of the documentation trail the user must navigate. |

## 12. Sample Data and Input Sources

| ID | Short | Rule |
|----|-------|------|
| 12.1 | Sample input included | The application MUST include or automatically download at least one sample input (e.g., video file, image, dataset) so the user can verify functionality without providing their own data. This rule is about a ready-to-use bundled/auto-downloaded sample — the mechanism to feed a live input is rule 12.2. |
| 12.2 | Simulated live input | If the application requires a live input (e.g., RTSP stream, sensor), the documentation MUST provide a command or container to simulate that input locally. A documented simulator satisfies this rule even if the user must point it at their own file; whether a ready-to-use sample is bundled is governed by rule 12.1. Do NOT fail both 12.1 and 12.2 for the same missing sample. |
| 12.3 | Sample data ≤ 500 MB | Sample data total size MUST NOT exceed 500 MB. Larger datasets MUST be optional. |

## 13. Security and Credentials

| ID | Short | Rule |
|----|-------|------|
| 13.1 | No default passwords | The application MUST NOT ship default passwords or tokens that grant access to external services. |
| 13.2 | Credential docs | If authentication is required between services, the documentation MUST explain how credentials are generated or rotated. |
| 13.3 | Non-root containers | All container images MUST run as a non-root user unless a documented technical exception exists. |
| 13.4 | Minimal port exposure | The application MUST NOT expose management ports (e.g., database, message broker) to the host network unless explicitly required by the use case. |

## 14. Logging and Observability

| ID | Short | Rule |
|----|-------|------|
| 14.1 | Structured logs to stdout | Each service MUST write structured logs (JSON or key-value) to stdout so `docker compose logs` shows unified output. |
| 14.2 | Ready message logged | The application MUST log a clear "ready" or "serving" message when initialization is complete. The AI agent MUST use this message to confirm successful startup. |
| 14.3 | No secrets in logs | Log output MUST NOT contain secrets, tokens, or full file paths from the build environment. |

## 15. Graceful Degradation and Error Handling

| ID | Short | Rule |
|----|-------|------|
| 15.1 | Optional service failure | If an optional service fails (e.g., telemetry collector), the core application MUST continue to operate and the UI MUST remain accessible. |
| 15.2 | Device fallback | If the configured inference device is unavailable, the application MUST fall back to the next available device (GPU → NPU → CPU) or display a clear error message. The application MUST NOT crash silently. |
| 15.3 | Input retry | If the input source is temporarily unavailable, the application MUST retry automatically and MUST NOT crash. |
| 15.4 | Specific error causes | Error messages shown to the user MUST distinguish between different failure causes (e.g., "cannot reach the source," "unsupported format," "connection timed out — retry"). Generic messages like "Stream not found" without actionable detail are not acceptable. |

## 16. UI and User Experience

| ID | Short | Rule |
|----|-------|------|
| 16.1 | Functional in browsers | The web UI MUST be functional and render correctly in modern browsers without errors that block user interaction. |
| 16.2 | Loading indicator | The UI MUST display a loading indicator or status message while models are loading or pipelines are initializing. |
| 16.3 | Self-explanatory UI | The UI MUST be usable without reading documentation — primary actions (start, stop, view results) MUST be discoverable within 30 seconds. |
| 16.4 | Version and status shown | The UI MUST display the application version and connection status to backend services. |
| 16.5 | Built-in local input | If the application processes live input (e.g., video, audio), the UI MUST offer a built-in option to use a local source (e.g., webcam, microphone, sample file) without requiring the user to set up external infrastructure. |

---

## Rationale for Key Thresholds

These values are engineering decisions based on practical constraints of the target environment. They are not derived from formal standards.

| Threshold | Value | Rationale |
|-----------|-------|-----------|
| Clone size (rule 1.2) | ≤ 100 MB | Most app folders are 1–20 MB. Some outliers (e.g., apps bundling large assets) reach 100+ MB — those need to move large files to container images or download scripts. |
| Clone time (rule 1.5) | < 2 min | 100 MB on 50 Mbps takes ~17s. 2 min gives margin for slow connections and git overhead. |
| External tools (rule 2.2) | Max 3 | The natural set for containerized deployment: git + Docker + Compose (or Helm + kubectl). Anything beyond this adds onboarding friction disproportionate to the benefit. |
| Full deploy (rule 4.1) | < 5 min | Practical upper bound for the application start command (excludes one-time model/image download per rule 4.4): a user waiting longer will context-switch or abandon. Validated against measurements from validation runs. |
| Steps (rule 5.1) | 3–4 steps | Base workflow: clone → run → verify. One optional automated step (model/data preparation) is allowed before deployment. This acknowledges that large model downloads (5–20 GB) are impractical to embed in `docker compose up` but must still be a single command — not a multi-step manual process. |
| UI ready (rule 7.2) | 60s | After healthy status, the app should serve immediately. 60s allows for deferred initialization (e.g., model loads on first request). Beyond that, users assume failure and refresh. |
| Images (rule 9.1) | ≤ 30 GB | 30 GB per app allows running multiple applications on the same host without filling the disk. |
| Sample data (rule 12.3) | ≤ 500 MB | Must be downloadable in ~2 min on the reference 50 Mbps connection. Enough for a meaningful demo (e.g., 30s video, small dataset). |
| UI discoverable (rule 16.3) | 30s | If a user opens the dashboard and cannot figure out how to start within 30s, the UI needs better labeling. Based on informal usability testing of similar tools. |
