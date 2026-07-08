---
name: sc-up
description: >
  Bring up the Flutter implementation with the existing Content Search backend.
  Runs the startup script at utils/flutter/start.ps1 and validates
  application health.
  Use when the user says "start smart classroom", "run the app", "launch smart
  classroom", "bring up services", or "open smart classroom".
---

# SC Up

Start the Flutter implementation against the existing Content Search backend.
**Agent: execute every command below directly using your terminal tool and relay
the output.**

---

## Workflow

### 1. Run startup script

```powershell
.\utils\flutter\start.ps1
```

**Note:** The startup script already includes backend health verification. No additional health check is needed.

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `start.ps1` not found | Script missing in `utils/flutter/` | Add script or correct path |
| Health endpoint unreachable | Backend not started by script | Run `sc-setup`, then rerun `sc-up` |

---

## Output

Report: **startup script launched** -> **health endpoint status**.
