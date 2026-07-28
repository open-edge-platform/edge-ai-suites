# OpenClaw — install & uninstall

Install and uninstall a **plain OpenClaw** — no demo, no plugins, no baked-in models.
You add your own models yourself — during onboarding (step 3) or later (step 4).

## Install

### 1. Pre-requisites

```bash
# Configure npm previledge
mkdir -p ~/.npm-global 
npm config set prefix '~/.npm-global'

# Node.js >= 24
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```
> If you have already met the requirements, please skip this step.

### 2. CLI

```bash

npm install -g openclaw@2026.7.1
openclaw --version
```
> This guide is verified against the pinned version `2026.7.1`. To try the latest release instead, run `npm install -g openclaw@latest`.

### 3. Onboard (creates `~/.openclaw` + the gateway service)

```bash
openclaw onboard --install-daemon
```

Wizard choices for a bare install (skip everything online — add it later):

| Step | Choose |
|---|---|
| Onboarding mode | **QuickStart** |
| Model / auth provider | **Configure now:** pick your model and enter its API key when prompted. **Skip:** choose *Skip for now* and add a model later. |
| Default model | **Configure now:** pick the model to use by default. **Skip:** *Keep current*. |
| Select channel | **Skip for now** |
| Search provider | **Tavily Search** (Tavily API key required) |
| Install Tavily plugin? | **Download from npm** |

> - For tavily serach, get an API Key: https://app.tavily.com/home (1,000 free credits per month)

Verify the gateway is up:

```bash
openclaw gateway status     # Runtime: running
openclaw dashboard          # opens the Control UI
```
> Read the gateway token in `openclaw.json` manually.

### 4. Reconfigure any time

If you skipped model setup during onboarding — or want to change the provider,
model, or API key later — rerun the guided config:

```bash
openclaw configure
```


## Uninstall

```bash
bash uninstall.sh        # interactive (asks whether to remove the CLI too)
bash uninstall.sh -y     # no prompts — also removes the npm CLI
```

Stops the gateway, runs `openclaw uninstall` (removes the systemd user service +
`~/.openclaw`), and strips the bash-completion line from `~/.bashrc` — backing up
`openclaw.json` and `~/.bashrc` first. It then removes the `openclaw` npm CLI too:
with `-y` directly, otherwise after a prompt.
