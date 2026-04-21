# Enable Alert Mode

Alert Mode is an optional feature in Live Video Captioning that enables alert-style visual feedback based on configurable keyword rules. When enabled, the application highlights run cards and caption panels with custom colors whenever a caption matches a user-defined keyword, making it ideal for automated monitoring and surveillance scenarios.

## Overview

In Alert Mode, the application:

- Updates the application title to "Live Video Captioning and Alerts"
- Reveals an **Alert Rules** panel in the dashboard where you define up to 3 keyword rules
- Applies distinct visual highlighting to the run card and caption panel whenever a caption contains a matching keyword
- Applies rules in priority order — the **first matching rule** wins for each caption update

This mode is particularly useful for:

- **Accident Detection**: Monitor traffic streams for incidents
- **Security Monitoring**: Detect unauthorized access or suspicious activity
- **Safety Compliance**: Verify safety protocols are being followed
- **Anomaly Detection**: Identify unusual events in video feeds

## Enabling Alert Mode

### Environment Variable in `.env` File

Add or modify the `ALERT_MODE` variable in your `.env` file:

```bash
# .env file
WHIP_SERVER_IP=mediamtx
WHIP_SERVER_PORT=8889
WHIP_SERVER_TIMEOUT=30s
PROJECT_NAME=live-captioning
HOST_IP=<HOST_IP>
EVAM_HOST_PORT=8040
EVAM_PORT=8080
DASHBOARD_PORT=4173
WEBRTC_PEER_ID=stream
ALERT_MODE=True   # Enable Alert Mode
CAPTION_HISTORY=3
```

## Configuring Alert Rules

When Alert Mode is active, an **Alert Rules** section appears in the dashboard sidebar. You can define up to **3 rules**, each consisting of:

| Field       | Description                                                                  |
| ----------- | ---------------------------------------------------------------------------- |
| **Keyword** | A plain-text substring to search for in each caption (case-insensitive)      |
| **Color**   | A highlight color (hex) applied to the run card and caption panel on a match |

Rules are evaluated **in order from top to bottom**. The first rule whose keyword is found in the caption text is applied; remaining rules are skipped for that caption.

### Rule Syntax

- Each rule matches a **single substring** — there is no regex or list syntax.
- Matching is **case-insensitive** and checks whether the keyword appears **anywhere** in the caption (e.g., the keyword `fire` also matches `campfire`).
- If no rule matches, no alert highlighting is applied.

### Example Rules

| Keyword  | Color              | Triggers when caption contains…          |
| -------- | ------------------ | ---------------------------------------- |
| `yes`    | `#ff4444` (red)    | "Yes", "yes", "YES", "yes, there is…"    |
| `fire`   | `#ff8800` (orange) | "fire", "Fire", "campfire", "fire truck" |
| `person` | `#ffaa00` (amber)  | "person", "Person", "a person walking"   |

### Persistence

Alert rules are automatically saved to your browser's **localStorage** under the key `lvc_alert_rules`. They are restored the next time you open the dashboard, so you do not need to re-enter them after a page refresh.

## Custom Prompts

Alert Mode works with any prompt — it is not limited to binary Yes/No responses. You can use any prompt whose output reliably contains predictable keywords that your rules can match.

Example prompts and corresponding rule keywords:

- **Binary detection**: "Is there a fire or smoke visible in the stream? Just Answer with a Yes or No"
  → Rule keyword: `yes`
- **Descriptive monitoring**: "Describe any safety hazards visible in the scene."
  → Rule keywords: `fire`, `smoke`, `hazard`
- **Crowd Detection**: "Is there a large crowd gathering?"
  → Rule keyword: `yes`
- **PPE Compliance**: "Is the person wearing a safety helmet? Answer Yes or No."
  → Rule keyword: `no`

## Next Steps

- [Get Started](../get-started.md) - Basic setup and configuration
- [API Reference](../api-reference.md) - REST API documentation
- [System Requirements](../get-started/system-requirements.md) - Hardware and software requirements
