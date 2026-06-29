/**
 * HTTP API client for the surgical-instrument backend.
 *
 * Endpoint surface mirrors NICU-Warmer so that lifted UI components, the
 * Redux store, and the SSE consumer can stay shape-compatible. Paths are
 * relative; nginx (prod) or Vite's dev proxy (dev) routes them to the backend.
 */

import type { Device, Source } from '../store/slices/controlSlice';

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error';
  build_sha?: string;
  uptime_s?: number;
}

export interface ReadinessResponse {
  ready: boolean;
  reasons?: string[];
}

export interface StatusResponse {
  lifecycle:
    | 'INITIALIZING'
    | 'PREPARING'
    | 'READY'
    | 'STARTING'
    | 'RUNNING'
    | 'STOPPING'
    | 'ERROR';
  message?: string;
  pipeline_instance_id?: string | null;
  device?: Device;
  source?: Source;
  threshold?: number;
}

export interface StartRequest {
  device: Device;
  source: Source;
  threshold: number;
}

export interface StartResponse {
  ok: boolean;
  instance_id?: string;
  message?: string;
}

export interface StopResponse {
  ok: boolean;
  message?: string;
}

class ApiError extends Error {
  constructor(public status: number, public path: string, message: string) {
    super(`${path} → ${status}: ${message}`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new ApiError(resp.status, path, text || resp.statusText);
  }
  if (resp.status === 204) return undefined as unknown as T;
  return (await resp.json()) as T;
}

export const api = {
  health:    () => request<HealthResponse>('/health'),
  readiness: () => request<ReadinessResponse>('/readiness'),
  status:    () => request<StatusResponse>('/status'),
  start:     (body: StartRequest) =>
    request<StartResponse>('/start', { method: 'POST', body: JSON.stringify(body) }),
  stop:      () => request<StopResponse>('/stop', { method: 'POST' }),

  /** URL helpers for stream tags (no fetch). */
  videoStreamUrl: () => '/video/stream',
  frameLatestUrl: (v?: number) => `/frame/latest${v !== undefined ? `?v=${v}` : ''}`,
};

export { ApiError };
