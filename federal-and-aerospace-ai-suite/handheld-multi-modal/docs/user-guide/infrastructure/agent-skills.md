<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# AI Agent Integration and Developer Experience

The Edge Node Infrastructure software ships a set of agent skills that let you run platform workflows through natural language, using GitHub Copilot or Claude Code. Instead of manually running scripts and commands, describe the outcome you want and the agent takes care of the rest.

Some skills are meant to run from the developer host, while others are meant to run directly on the provisioned host.

## Available Skills

| Skill | What it does | Execution target |
|---|---|---|
| `create-image` | Builds a host OS image using the Image Composer Tool or ISO based curation | Developer host |
| `create-usb-installation-files` | Packages a complete bootable USB artifact (`usb-installation-files.tar.gz`), optionally running `create-image` first | Developer host |
| `validate-platform-config` | Validates a provisioned edge node — checks k3s pod health, binary paths, cloud-init state, network/proxy settings, and device readiness (GPU VFs, NPU) | Provisioned host |
| `update-install-packages` | Updates Ubuntu package configuration and installs required packages on a provisioned system | Developer host |
| `set-power-profile` | Sets the platform power envelope — a named profile (LowPower 10 W, BalancedLow 15 W, BalancedHigh 20 W, Performance 25 W, MaxPerformance) or a custom PkgWatt (PL1) / SysWatt (psys) envelope with burst ratio and time window | Provisioned host |
| `set-thermal-profile` | Sets the thermald thermal escalation policy — generates, validates, applies, and verifies staged Fan/Processor/powerclamp trip points (cool, warm, hot, thermal-max, or custom) | Provisioned host |
| `monitor-power-thermal` | Monitors package temperature and RAPL power domains and logs results (`pt_mon.txt`) | Provisioned host |
| `generate-platform-stress` | Generates configurable CPU and integrated-GPU load with stress-ng — control worker count, per-CPU load percentage, GPU worker count, and duration | Provisioned host |
| `generate-openvino-stress` | Generates sustained AI inference load on CPU, GPU, or NPU using OpenVINO `benchmark_app` in a K3s pod or Docker container for realistic power/thermal qualification | Provisioned host |
| `combined-power-thermal-profiling` | Orchestrates a full profiling session — chains set-power-profile → set-thermal-profile → monitor-power-thermal → generate-platform-stress and emits one consolidated enclosure report with a throttle/headroom verdict | Provisioned host |

## How to Use Skills

Open GitHub Copilot Chat or Claude Code in the repository workspace and describe what you want in natural language. The agent matches your request to the appropriate skill, asks for any missing inputs, then runs the workflow. These skills have been verified from a developer system and, where applicable, against a provisioned target system.

For skills marked as **Provisioned host**, run the agent CLI directly on the provisioned host after installing and authenticating it. The repository code and skill scripts are available on provisioned systems at `/opt/edge/developer`.

Brief example (Claude CLI on target host):

```bash
# 1) Install Claude CLI on the provisioned host
curl -fsSL https://claude.ai/install.sh | sh

# 2) Configure credentials/authentication before running skills
export PATH="$HOME/.local/bin:$PATH"
claude --version
claude auth login
```

### Example Prompts

```text
Build an OS image for my Intel Core Ultra system.
```

```text
Create a bootable USB artifact using the ICT image at /path/to/image.raw.gz.
```

```text
Validate this provisioned node — check pods, drivers, proxy settings, and GPU VFs.
```

```text
Add sysbench and stress-ng to ict-template only for a debug image variant.
```

### What the Agent Does

For every skill invocation the agent follows this fixed sequence:

1. **Collects required inputs** — prompts for anything not provided in the request
2. **Runs preconditions** — verifies the environment is ready before making any changes
3. **Executes steps** — runs the workflow, pausing for confirmation before any privileged or destructive action
4. **Validates results** — confirms the expected artifacts or system state are present
5. **Reports outcome** — returns artifact paths, validation status, and troubleshooting notes on failure

> **Note:** The agent will never proceed past a failed precondition or skip the validation step.
