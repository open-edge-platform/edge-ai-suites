
This folder contains the React UI for the Smart Classroom Application.

## Quick start
1. Install **Node 18+**
2. `npm install`
3. `npm run dev` 
4. `npm run build` → static files in `dist/`

## Electron desktop app (optional)

The UI can also run as a Windows desktop app. This is an **additive** layer
(see [`electron/`](electron/)): the web-app workflow above is unchanged, and the
Electron build consumes the same `dist/` output from `npm run build`.

Unlike the web app, the desktop app **supervises the Python services itself** —
it starts and stops them, tails their logs, edits the configuration files and
runs first-time setup. Launch it from the repo root of the component:

```powershell
..\start-desktop-app.ps1
```

That script bootstraps Node (installing it via `winget` when missing), rebuilds
`dist/`, and hands over. It never requests Administrator privileges.

| Screen | Backed by |
|--------|-----------|
| **Setup** | [`electron/services/setup-runner.cjs`](electron/services/setup-runner.cjs) — prerequisite checks, Python environment, model preparation |
| **Configuration** | [`electron/services/config-store.cjs`](electron/services/config-store.cjs) — comment-preserving writes to `config.yaml`, `runtime_config.yaml`, `.proxy-config` |
| **Services** | [`electron/services/process-manager.cjs`](electron/services/process-manager.cjs) — spawns `main.py`, health-polls it and every service it starts, stops the tree |

How it reaches the backends: the main API (8000) is CORS-enabled, so calls go to
it directly. Content-search (9011) has no CORS, so like the Vite dev proxy,
the packaged app serves the UI from a local origin and proxies `/api/v1` to
`127.0.0.1:9011` via a small embedded server ([`electron/server.cjs`](electron/server.cjs)).

| Command | What it does |
|---------|--------------|
| `npm run electron:dev` | Runs the Vite dev server + Electron pointed at it (hot reload). |
| `npm run electron:preview` | Builds `dist/` and runs Electron through the production path (embedded static + proxy server) without packaging. |
| `npm run electron:build` | Builds `dist/` and packages a Windows portable executable to `release/SmartClassroom-<version>-portable.exe`. |

### Main-process architecture

Everything that touches the OS lives in the main process; the renderer only ever
names things. Two rules make that safe:

- **The renderer cannot supply a command line.** It sends a service id, a config
  path or a step/action id. Each is validated against a static table
  ([`registry.cjs`](electron/services/registry.cjs),
  [`config-schema.cjs`](electron/services/config-schema.cjs),
  [`setup-runner.cjs`](electron/services/setup-runner.cjs)) before anything runs.
- **Every IPC handler checks the sender** is the app's own window, and replies
  with an `{ ok, data } | { ok, error }` envelope carrying a message only — never
  a stack trace. See [`electron/services/ipc.cjs`](electron/services/ipc.cjs).

Secrets never cross the boundary: `models.asr.hf_token` is reported to the UI as
"set" or "not set", and is only written when the user types a replacement.

`contextIsolation`, `sandbox` and `webSecurity` are on; `nodeIntegration` is off.

## Core dependencies

| Package               | Purpose                                   |
|-----------------------|-------------------------------------------|
| `react` / `react-dom` | UI library and renderer                   |
| `@reduxjs/toolkit`    | Redux store + slices                      |
| `react-redux`         | React bindings for Redux                  |
| `axios`               | HTTP client                               |
| `react-i18next`       | Translations (`src/i18n/`)                |
| `video.js` / `react-player` | Video playback                      |
| `jsmind`              | Mind map rendering                        |
| `pdfjs-dist`          | PDF preview                               |
| `express` / `http-proxy-middleware` | Embedded static + proxy server for the packaged Electron app |
| `yaml`                | Comment-preserving config edits (main process) |

## State & data flow

1. **Redux Toolkit**  
   - Slices: `ui`, `transcript`, `summary`, `mindmap`, `resource`, `classStatistics`,
     `mediaValidation`, `featureConfig`  
   - Typed hooks: `useAppDispatch()` / `useAppSelector()`

2. **Data fetching**  
   - REST calls wrapped in `services/api.ts` (axios + `fetch` for streamed responses)  
   - Long-running pipelines are followed by polling and server-sent events, not sockets  
   - Electron-only bridges live alongside them: `services/serviceManager.ts`,
     `services/configManager.ts`, `services/setupManager.ts`

