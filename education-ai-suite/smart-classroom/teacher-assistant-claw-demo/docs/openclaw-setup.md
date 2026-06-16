# OpenClaw setup for Teacher Assistant demo

The OpenClaw based agent functions as the "Teacher Assistant" persona that enables the staff of a school, which includes teachers, to create their own custom report based on the per classroom data provided by the Smart Classroom application. The custom report can be at a class level or at a grade level combining all classrooms in that grade and at the school level which combines all the grades. The deployment setup envisaged is shown in the figure below.

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Teacher Assistant Demo                        │
│  ┌──────────┐     ┌─────────────────┐    ┌──────────────────────┐    │
│  │   SC-1   │◄───►| OpenClaw Agent  │◄──►│       Telegram       │    │
│  └──────────┘     │                 │    │ Channel based comms  |    │   
│  ┌──────────┐     │                 │    └──────────────────────┘    │
│  │   SC-2   │◄───►│                 │                                │
│  └──────────┘     │                 │    ┌──────────────────────┐    │
│  ┌──────────┐     │                 │───►|      OVMS local      |    │
│  |   SC-n   │◄───►│                 │    |       inference      |    │
│  └──────────┘     └─────────────────┘    └──────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

```
Note: In the figure, Smart Classroom is abbreviated as SC.

## ✅ Pre-requisites

### System Requirements for OpenClaw agent
- Ubuntu 24.04 LTS
- Intel PTL based system 
- At least 32GB RAM
- 100GB free disk space for models and environments

### Smart Classroom setup
It is assumed here that Smart Classroom application is setup in a separate node compared to OpenClaw Agent. The WSL route of installing OpenClaw in a Windows environment and hence sharing the same compute resources with Smart Classroom app is not covered in this version. The set-up of the Smart Classroom is as per the documentation provided in the Smart Classroom application repo. This documentation is not repeated here. Communication between the Smart Classroom app and OpenClaw is covered in this documentation.

### Prepare for setup

The following tools must be available on the system:
- **Docker** — installed and running ([install guide](https://docs.docker.com/engine/install/ubuntu/))
- **git** — for cloning the repository
- **curl** — for installing OpenClaw and checking OVMS status

---

## ⚙️ Setup OVMS

OVMS should be setup before OpenClaw installation to ensure easy discoverability and configuration. Run the following script to start OVMS and wait for the model to be loaded:

``` bash
chmod +x ./setup-ovms.sh &&
./setup-ovms.sh
```

> **Note:** The first run downloads the model (~5GB) which may take 5–10 minutes. The script will wait automatically until the model is ready.

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

### Step 2: OpenClaw installation

Quickly install OpenClaw using the following command. The version of OpenClaw can be changed as per the requirement.

``` bash
curl -fsSL https://openclaw.ai/install.sh | bash -s -- --version 2026.6.6 --no-onboard
```

---

### Step 3: Configure OpenClaw

Apply configuration from the repo and restart the gateway for the changes to take effect:

``` bash
openclaw config patch --file ./openclaw-config.json &&
openclaw gateway install
```

<details>
<summary>Useful debugging commands</summary>

``` bash
openclaw gateway status
openclaw status
openclaw config get gateway.auth.token
```

</details>

---

### Step 4: Deploy workspace files

Copy the workspace configuration files (SOUL.md, AGENTS.md, SKILL.md) to the OpenClaw workspace directory. These files define the agent persona, available agents, and skills.

``` bash
chmod +x ./setup-openclaw-workspace.sh &&
./setup-openclaw-workspace.sh &&
openclaw skills update
```

The `openclaw skills update` command registers the deployed skill with OpenClaw so it becomes available during chat and dashboard sessions.

<details>
<summary>Workspace structure created by the script</summary>

```
~/.openclaw/workspace/
├── SOUL.md                          # Agent persona and behavior
├── AGENTS.md                        # Agent definitions
├── smart_classroom_incoming/        # Data directory for Smart Classroom reports
│   ├── lesson1.md                   # Sample flat-file session (legacy format)
│   └── 2026-06-10/                  # Sample session folder
│       ├── summary.md
│       ├── topics.json
│       ├── engagement_report.json
│       └── participation_report.json
└── skills/
    └── classroom_qa/
        └── SKILL.md                 # Smart Classroom QA skill definition
```

</details>

> **Note:** The `~/.openclaw/workspace/smart_classroom_incoming/` directory is where the Smart Classroom application deposits lesson reports for the agent to analyze. You can add additional session folders there at any time — the agent will pick them up automatically.

---

### Step 5: Run OpenClaw agent

Run the following commands to start the OpenClaw agent in the web dashboard or terminal:

``` bash
# Run the agent in the web dashboard
openclaw dashboard

# Or run the agent in the terminal
openclaw chat
```

Try the following example prompt to verify the agent can read the sample session data:

```
Summarize the lesson from June 10
```

---

## 📚 Learn More

- [OpenClaw]()
- [Smart Classroom]()
