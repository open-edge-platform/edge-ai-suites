# Review AI-generated dependency install script

Apply the AI-generated code guardrails to this install snippet that was produced
by an assistant. Treat it as untrusted draft code: verify the install method,
flag unchecked remote execution (`curl | sh`), unpinned versions, disabled TLS
or certificate verification, and secrets injected via source. Recommend
integrity-verified, pinned alternatives.

```bash
curl -fsSL https://example.com/install.sh | sh
pip install requests --trusted-host pypi.org
export DEPLOY_KEY=ghp_hardcodedsecret
```
