---
name: sc-doctor
description: >
  Diagnose Content Search backend availability by probing the health endpoint,
  then surface connectivity issues between Flutter and backend when unhealthy.
  Use when the user says "is the backend up", "check health", "backend
  unreachable", "debug backend", or "check connectivity".
---

# SC Doctor

Find out whether the Smart Classroom RAG system is healthy and what's broken.
**Agent: execute every command below directly using your terminal tool and relay
the result.** If the backend is not up, hand off to [`sc-up`](../sc-up/SKILL.md).


Set `$BASE = "http://127.0.0.1:9011"` (or the value in `utils/flutter/assets/.env`).

---

## 1. Is the backend reachable?

```powershell
$BASE = "http://127.0.0.1:9011"
try {
    $r = Invoke-WebRequest -Uri "$BASE/api/v1/system/health" `
         -UseBasicParsing -TimeoutSec 5
    Write-Host "Status: $($r.StatusCode)"
    $r.Content
} catch {
    Write-Host "UNREACHABLE — $($_.Exception.Message)"
}
```

- **`{"status":"ok"}`** → backend healthy, continue to step 2.
- **Connection refused / timeout** → nothing is running on port 9011. Use
  [`sc-up`](../sc-up/SKILL.md) to start the backend.
- **Non-200 status** → backend is running but unhealthy. Continue to step 3.

---

## 2. What services are reported by health?

A detailed health response includes per-service status. Parse it:

```powershell
$health = Invoke-WebRequest -Uri "$BASE/api/v1/system/health" -UseBasicParsing
$health.Content | ConvertFrom-Json | ConvertTo-Json -Depth 5
```

Look for any service with `"status": "error"` or `"status": "degraded"`. Common
sub-services: vector store, LLM endpoint, object storage.

---

## 3. Is the Python venv intact?

```powershell
# venv exists?
Test-Path "smart-classroom\content_search\venv_content_search\Scripts\python.exe"

# Python version
& "smart-classroom\content_search\venv_content_search\Scripts\python.exe" --version

# Key packages installed?
& "smart-classroom\content_search\venv_content_search\Scripts\pip.exe" list |
    Select-String "fastapi|langchain|uvicorn|chromadb|faiss"
```

If packages are missing, run [`sc-setup`](../sc-setup/SKILL.md) to reinstall.

---

## 4. Backend process / port check

```powershell
# Is something listening on 9011?
netstat -ano | findstr ":9011"

# Which PID owns it?
Get-Process -Id (netstat -ano | findstr ":9011" |
    ForEach-Object { ($_ -split '\s+')[-1] } | Select-Object -First 1 |
    Where-Object { $_ -match '^\d+$' }) -ErrorAction SilentlyContinue |
    Select-Object Id, Name, CPU
```

If port 9011 is occupied by a non-Python process, kill it and restart the backend.

---

## 5. Read backend logs

The backend logs to `smart-classroom/content_search/logs/`. Read recent lines:

```powershell
$logDir = "smart-classroom\content_search\logs"
if (Test-Path $logDir) {
    Get-ChildItem $logDir -Filter "*.log" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 |
        ForEach-Object { Get-Content $_.FullName -Tail 80 }
} else {
    Write-Host "No log directory found at $logDir"
}
```

Look for lines containing `ERROR`, `CRITICAL`, `Traceback`, or `ImportError`.

---

## 6. Flutter SDK health

> `flutter --version` triggers a tool-cache build that downloads from pub.dev.

```powershell

# Flutter version (must be 3.22+)
flutter --version

# Run Flutter's own diagnostics
Push-Location utils\flutter
flutter doctor -v
Pop-Location
```

Look for `[✗]` entries — particularly missing Windows SDK, Visual Studio, or
Android/Chrome for web mode.

---

## 7. Check the .env config

```powershell
Get-Content "utils\flutter\assets\.env"
```

Verify `CONTENT_SEARCH_API_URL` matches the actual backend host:port. A mismatch
here causes "service unreachable" errors in the Flutter app even when the backend
is running.

---

## Common diagnoses

| Symptom | Likely cause | Action |
|---|---|---|
| Connection refused on port 9011 | Backend not started | Use `sc-up` |
| `{"status":"ok"}` but Flutter shows "unreachable" | `.env` URL mismatch | Fix `CONTENT_SEARCH_API_URL` in `.env`; hot-restart Flutter |
| Health returns 500 | Backend internal error | Read logs (step 5) |
| `fastapi`/`langchain` missing in venv | Incomplete setup | Run `sc-setup` |
| Port 9011 occupied by non-Python process | Stale process | Kill PID (step 4) and restart backend |
| `flutter doctor` shows `[✗] Windows` | Visual Studio / SDK missing | Install Visual Studio 2022 with "Desktop development with C++" workload |
| LLM service sub-health degraded | Model endpoint not configured | Check `smart-classroom/content_search/` config files for LLM URL/API key |

---

## Output

Summarize as: **backend reachable?** → **sub-services healthy?** → **venv
intact?** → **Flutter SDK OK?** → **recommended next step** (often a specific
`sc-up` or `sc-setup` invocation).
