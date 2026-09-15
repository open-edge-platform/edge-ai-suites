# OpenClaw — install & uninstall

Install and uninstall a **plain OpenClaw** — no demo, no plugins, no baked-in models.
You add your own models yourself — during onboarding (step 3) or later (step 4).

## Install

### 1. Pre-requisites

```bash
# Configure a user-owned npm install location.
mkdir -p "$HOME/.npm-global"
npm config set prefix "$HOME/.npm-global"
export PATH="$HOME/.npm-global/bin:$PATH"
grep -qxF 'export PATH="$HOME/.npm-global/bin:$PATH"' "$HOME/.bashrc" || \
	echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME/.bashrc"

# OpenClaw 2026.7.1 supports Node.js >=22.22.3 <23, >=24.15.0 <25, or >=25.9.0.
# This recipe installs the supported 22.x line.
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


## Proxy Configuration

The gateway runs as a systemd **user service**, so it does not inherit the proxy
variables from your login shell. Without them `web_search` / `web_fetch` fail
with `request timed out` even though Tavily is configured correctly.

```bash
bash configure_proxy.sh              # menu: configure / clear / status
bash configure_proxy.sh configure    # reuse http_proxy/https_proxy/no_proxy from the shell, else ask
bash configure_proxy.sh clear        # remove the proxy from the gateway only
bash configure_proxy.sh status       # show the drop-in + the running gateway's env
```

Writes a systemd drop-in at `~/.config/systemd/user/openclaw-gateway.service.d/proxy.conf`
and restarts the gateway. `localhost,127.0.0.1,::1` is always appended to
`no_proxy` so the local model and MCP endpoints stay direct. The system / shell
proxy configuration is never modified.

## Uninstall

```bash
bash uninstall.sh        # interactive (asks whether to remove the CLI too)
bash uninstall.sh -y     # no prompts — also removes the npm CLI
```

Stops the gateway, runs `openclaw uninstall` (removes the systemd user service +
`~/.openclaw`), and strips the bash-completion line from `~/.bashrc` — backing up
`openclaw.json` and `~/.bashrc` first. It then removes the `openclaw` npm CLI too:
with `-y` directly, otherwise after a prompt.
