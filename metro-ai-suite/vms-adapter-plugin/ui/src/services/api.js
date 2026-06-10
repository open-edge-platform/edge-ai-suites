// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

/**
 * VMS Plugin Service API client.
 *
 * In dev: Vite proxies /v1 → VITE_API_BASE (default http://localhost:8085).
 * In production: nginx routes /v1 → http://backend:8080 via Docker service DNS.
 */

const BASE = '/v1';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

/** Backend Camera model uses `name`; UI uses `camera_name`. */
function normaliseCamera(cam) {
  return {
    ...cam,
    camera_name: cam.name ?? cam.camera_name ?? cam.camera_id,
  };
}

// ── Health ────────────────────────────────────────────────────────────────────

/** GET /v1/ready — readiness probe. */
export async function getReady() {
  return request('/ready');
}

// ── Cameras ───────────────────────────────────────────────────────────────────

/** GET /v1/cameras — list all cameras stored in DB. */
export async function listCameras() {
  const data = await request('/cameras');
  return data.map(normaliseCamera);
}

/** POST /v1/cameras/discover — active scan across all NVRs (up to 30 s). */
export async function discoverCameras() {
  const data = await request('/cameras/discover', { method: 'POST' });
  return data.map(normaliseCamera);
}

/** POST /v1/cameras/enable — enable or disable cameras by ID. */
export async function setCameraEnabled(cameraIds, enabled) {
  return request('/cameras/enable', {
    method: 'POST',
    body: JSON.stringify({ camera_ids: cameraIds, enabled }),
  });
}

// ── Analytics Apps — generic run lifecycle ────────────────────────────────────────

/**
 * GET /v1/analytics-apps/discover — list all registered Analytics Apps with their
 * Pydantic JSON Schemas and live availability.
 */
export async function discoverAnalyticsApps() {
  const data = await request('/analytics-apps/discover');
  return Array.isArray(data) ? data : [];
}

/**
 * GET /v1/analytics-apps/:appId/options/:optionType
 * Returns a list of strings (models, pipelines, …) for dropdown population.
 */
export async function getAnalyticsAppOptions(appId, optionType) {
  return request(`/analytics-apps/${encodeURIComponent(appId)}/options/${encodeURIComponent(optionType)}`);
}

/** GET /v1/analytics-apps/:appId/runs — list active runs for any analytics app. */
export async function listAnalyticsAppRuns(appId) {
  const data = await request(`/analytics-apps/${encodeURIComponent(appId)}/runs`);
  return (Array.isArray(data) ? data : []).map((r) => ({
    ...r,
    webrtcUrl: r.webrtcUrl || (r.peerId ? `/whep/${r.peerId}/whep` : ''),
  }));
}

/** DELETE /v1/analytics-apps/:appId/runs/:runId — stop a run for any analytics app. */
export async function stopAnalyticsAppRun(appId, runId) {
  return request(
    `/analytics-apps/${encodeURIComponent(appId)}/runs/${encodeURIComponent(runId)}`,
    { method: 'DELETE' },
  );
}

/**
 * POST /v1/analytics-apps/:appId/runs — validate the payload via the backend's
 * dynamic Pydantic model and trigger the analytics run.
 *
 * Throws an error with:
 *   .status      — HTTP status code
 *   .fieldErrors — array of {loc, msg, type} on 422 responses
 *   .message     — human-readable error string
 */
export async function startAnalyticsApp(appId, payload) {
  const res = await fetch(`${BASE}/analytics-apps/${encodeURIComponent(appId)}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload ?? {}),
  });
  if (!res.ok) {
    let detail;
    try { detail = (await res.json()).detail; } catch { detail = res.statusText; }
    const msg = res.status === 503
      ? `Schema not loaded: ${typeof detail === 'string' ? detail : 'call Discover Apps first'}`
      : res.status === 502
        ? `Analytics app error: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`
        : typeof detail === 'string' ? detail : 'Validation failed';
    const err = new Error(`API ${res.status}: ${msg}`);
    err.status = res.status;
    err.fieldErrors = Array.isArray(detail) ? detail : [];
    throw err;
  }
  return res.json();
}
