# OpenClaw Setup for Teacher Assistant Demo

The OpenClaw-based agent functions as the "Teacher Assistant" persona that enables teachers and school staff to query and generate custom reports from classroom session data. This guide sets up a **local, standalone demo** using sample session data and OVMS for on-device inference.

```
┌─────────────────────────────────────────────────────────┐
│                  Teacher Assistant Demo                 │
│                                                         │
│  ┌──────────────────┐    ┌──────────────────────────┐   │
│  │  OpenClaw Agent  │───►│      OVMS local          │   │
│  │                  │    │       inference          │   │
│  │ ┌──────────────┐ │    │  (Qwen3-8B on GPU)       │   │
│  │ │ Dashboard /  │ │    └──────────────────────────┘   │
│  │ │ Chat UI      │ │                                   │
│  │ └──────────────┘ │    ┌──────────────────────────┐   │
│  │                  │◄── │   Sample session data    │   │
│  └──────────────────┘    │(smart_classroom_incoming)│   │
│                          └──────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

> **ℹ️ This is the _basic_ setup variant** — the fastest, validated path to a working agent (OVMS local inference plus the OpenClaw dashboard/chat), **without external integrations**. It uses the configuration file [`openclaw-basic.json`](../openclaw-basic.json).

## ✅ Pre-requisites

### System Requirements
- Ubuntu 24.04 LTS
- Intel PTL based system
- At least 32GB RAM
- 100GB free disk space for models and environments

### Required tools

The following tools must be available on the system:
- **Docker** — installed and running ([install guide](https://docs.docker.com/engine/install/ubuntu/))
- **git** — for cloning the repository
- **curl** — for installing OpenClaw and checking OVMS status

---

## ⚙️ Setup OVMS

OVMS should be setup before OpenClaw installation to ensure easy discoverability and configuration. Run the following script to start the OVMS container in the background:

``` bash
./setup-ovms.sh
```

> **Note:** The first run downloads the model (~5GB). The download happens in the background while you proceed with Steps 1–2. The model will be ready by the time you reach Step 3.

---

## 🚀 Setup OpenClaw

Perform the following steps to setup OpenClaw agent for the Teacher Assistant demo.

---

### Step 1: Clone the repository

Clone the repository and navigate to the Teacher Assistant demo directory. All subsequent commands assume you are in this directory.

``` bash
git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git &&
cd edge-ai-suites &&
git sparse-checkout set education-ai-suite/smart-classroom/teacher-assistant-claw-demo &&
cd education-ai-suite/smart-classroom/teacher-assistant-claw-demo
```

---

### Step 2: Install and configure OpenClaw

Install OpenClaw, apply configuration from the repo, start the gateway, deploy the workspace, and wait for OVMS to finish loading the model:

``` bash
curl -fsSL https://openclaw.ai/install.sh | bash -s -- --version 2026.6.6 --no-onboard &&
openclaw config patch --file ./openclaw-basic.json &&
openclaw gateway install &&
./setup-openclaw-workspace.sh &&
openclaw skills update &&
echo "Waiting for OVMS..." &&
until curl -s http://localhost:8000/v3/models | grep -q "Qwen3-8B-int4-ov"; do sleep 5; printf "."; done
```

<details>
<summary>Useful debugging commands</summary>

``` bash
openclaw gateway status
openclaw status
openclaw config get gateway.auth.token
```

</details>


<details>
<summary>Workspace structure created by the script</summary>

```
~/.openclaw/workspace/
├── SOUL.md                          # Agent persona and behavior
├── AGENTS.md                        # Agent definitions
├── smart_classroom_incoming/        # Data directory for session reports
│   └── 2026-06-15/                  # Sample session folder
│       ├── summary.md
│       ├── topics.json
│       ├── engagement_report.json
│       └── session_meta.json
└── skills/
    └── classroom_qa/
        └── SKILL.md                 # Smart Classroom QA skill definition
```

</details>

> **Note:** The `~/.openclaw/workspace/smart_classroom_incoming/` directory is where session reports are stored for the agent to analyze. Sample data is included for testing. You can add additional session folders there at any time — the agent will pick them up automatically.

---

### Step 3: Run OpenClaw agent

Start the agent:

``` bash
openclaw chat
```

Try the following example prompt to verify the agent can read the sample session data:

```
Summarize the lesson from June 15
```

---

## 📚 Learn More

- [OpenClaw](https://openclaw.ai)
