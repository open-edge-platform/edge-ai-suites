---
name: sc-up
description: >
  Bring up the Flutter implementation with the existing Content Search backend.
  Runs the startup script at utils/flutter/start.ps1 and validates
  application health.
  Use when the user says "start smart classroom", "run the app", "launch smart
  classroom", "bring up services", or "open smart classroom".
license: Apache-2.0
metadata:
  version: "1.0.0"
  tags: "sc flutter startup"
---

<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

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

### 2. Verify backend health endpoint

```powershell
$BASE = "http://127.0.0.1:9011"
Invoke-WebRequest -Uri "$BASE/api/v1/system/health" -UseBasicParsing |
  Select-Object -ExpandProperty Content
```

### 3. Verify Flutter app is running

```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $_.LocalPort -in 5173,9011 } |
  Select-Object LocalAddress, LocalPort, OwningProcess
```

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `start.ps1` not found | Script missing in `utils/flutter/` | Add script or correct path |
| Health endpoint unreachable | Backend not started by script | Run `sc-setup`, then rerun `sc-up` |
| Flutter app not listening | Flutter process failed to start | Check terminal logs and rerun script |

---

## Output

Report: **startup script launched** -> **health endpoint status** ->
**ports listening**.
