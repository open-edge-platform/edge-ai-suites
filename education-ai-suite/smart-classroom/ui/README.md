
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

> **Prerequisite:** the Electron app packages the UI only. The backends must
> already be running.

How it reaches the backends: the main API (8000) is CORS-enabled, so calls go to
it directly. Content-search (9011) has no CORS, so like the Vite dev proxy,
the packaged app serves the UI from a local origin and proxies `/api/v1` to
`127.0.0.1:9011` via a small embedded server ([`electron/server.cjs`](electron/server.cjs)).

| Command | What it does |
|---------|--------------|
| `npm run electron:dev` | Runs the Vite dev server + Electron pointed at it (hot reload). |
| `npm run electron:preview` | Builds `dist/` and runs Electron through the production path (embedded static + proxy server) without packaging. |
| `npm run electron:build` | Builds `dist/` and packages a Windows portable executable to `release/SmartClassroom-<version>-portable.exe`. |

## Core dependencies

| Package               | Purpose                                   |
|-----------------------|-------------------------------------------|
| `react`               | UI library                                |
| `react-dom`           | React renderer                            |
| `@reduxjs/toolkit`    | Redux store + slices                      |
| `react-redux`         | React bindings for Redux                  |
| `@tanstack/react-query` | Data fetching & caching                 |
| `axios`               | HTTP client                               |
| `socket.io-client`    | Real-time WebSocket                       |

## State & data flow

1. **Redux Toolkit**  
   - Slices: `recording`, `file`, `ui`, `project`, `summary`, `transcript`, `resource`  
   - Typed hooks: `useAppDispatch()` / `useAppSelector()`

2. **React Query (TanStack)**  
   - REST calls wrapped in `services/api.ts`  
   - WebSocket updates push into `queryClient.setQueryData()` inside `services/socket.ts`

