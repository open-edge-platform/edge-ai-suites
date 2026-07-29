# OpenClaw Setup for Teacher Assistant Demo

The OpenClaw-based agent functions as the "Teacher Assistant" persona that enables teachers and school staff to query and generate custom reports from classroom session data. This guide sets up a **local, standalone demo** using sample session data and OVMS for on-device inference.

> **Data note:** This demo uses sample input data from `workspace/smart_classroom_incoming`. You can add your own data to `~/.openclaw/workspace/smart_classroom_incoming` for custom analysis.

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

> **ℹ️ This is the _basic_ setup variant** — the fastest, validated path to a working agent (OVMS local inference plus the OpenClaw dashboard/chat), **without external integrations**. It uses the configuration file [`openclaw-basic.json`](./openclaw-basic.json).

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

## 🚀 Setup OpenClaw

Perform the following steps to setup OpenClaw agent for the Teacher Assistant demo.

> **Tip:** Copy and run each command block as a whole.  
> Commands use `&&`, so the next command runs only if the previous one succeeds.

---

### Step 1: Clone the repository

Clone the repository and navigate to the Teacher Assistant demo directory. All subsequent commands assume you are in this directory.

``` bash
git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git &&
cd edge-ai-suites &&
git sparse-checkout set education-ai-suite/teacher-assistant-claw-demo &&
cd education-ai-suite/teacher-assistant-claw-demo
```

---

### Step 2: Setup OVMS

Run the following script to start the OVMS container in the background:

``` bash
./setup-ovms.sh
```

> **Note:** The first run downloads the model (~5GB), so this step may take a few minutes.

---

### Step 3: Install and configure OpenClaw

Install OpenClaw, apply configuration from the repo, start the gateway, and deploy the workspace:

``` bash
curl -fsSL https://openclaw.ai/install.sh | bash -s -- --version 2026.6.6 --no-onboard &&
openclaw config patch --file ./openclaw-basic.json &&
openclaw gateway install &&
./setup-openclaw-workspace.sh &&
openclaw skills update
```

---

### Step 4: Run OpenClaw agent

Start the agent. This waits for the model to finish loading, then opens the chat:

``` bash
./run-agent.sh
```

If the model isn't ready in time, the script stops with clear next steps on screen (see `Troubleshooting`).

Try this example prompt to verify the agent works:

```
Summarize the lesson from June 15
```

---

## 🛠️ Troubleshooting

If OVMS model download stops with an HTTP/2 stream error, first check logs to identify the cause, then rerun setup:

``` bash
docker logs --tail 200 teacher-assistant-ovms
./setup-ovms.sh
```

Then rerun Step 4.

---

## 📚 Learn More

- [OpenClaw](https://openclaw.ai)
