// src/services/api.ts
export type WorkloadType = 'rppg' | 'ai-ecg' | 'mdpnp' | '3d-pose' | 'all';
export type StreamingStatus = { locked: boolean; remaining_seconds: number };
export type StartResponse = { 
  status: string;
  message?: string;
};
export type StopResponse = { status: string; message: string };
export type ReadinessResponse = {
  lifecycle: string;
  ready: boolean;
  checks: Record<string, boolean>;
  errors: Array<{ code: string; message: string }>;
  last_error?: string | null;
};

// Derive API base URL from env or the host the UI is served from
const API_HOST = import.meta.env.VITE_API_HOST || window.location.hostname;
const API_PORT = import.meta.env.VITE_API_PORT || '5001';
const BASE_URL = import.meta.env.VITE_API_BASE_URL || `${window.location.origin}/api`;
const AGGREGATOR_URL = BASE_URL;

// console.log('[API] Aggregator URL:', AGGREGATOR_URL);
// console.log('[API] Metrics URL:', METRICS_URL);

// console.log('[API] BASE_URL configured as:', BASE_URL);
// console.log('[API] Environment variables:', import.meta.env);
const HEALTH_TIMEOUT_MS = 10000;

async function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) => setTimeout(() => reject(new Error('timeout')), ms))
  ]);
}

export async function safeApiCall<T>(apiCall: () => Promise<T>): Promise<T> {
  try {
    return await apiCall();
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error('Backend server is unavailable. Please ensure the aggregator is running.');
    }
    throw error;
  }
}

export async function pingBackend(): Promise<boolean> {
  try {
    const res = await withTimeout(
      fetch(`${BASE_URL}/health`, { cache: 'no-store' }),
      HEALTH_TIMEOUT_MS
    );
    if (!res.ok) return false;
    const data = await res.json();
    return data.status === 'healthy' || data.status === 'ok';
  } catch {
    return false;
  }
}

export async function getStreamingStatus(): Promise<StreamingStatus> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/status`, { cache: 'no-store' });
    if (!res.ok) {
      return { locked: false, remaining_seconds: 0 };
    }
    const data = await res.json();
    const lifecycle = data?.lifecycle;
    const locked = lifecycle === 'starting' || lifecycle === 'running';
    return { locked, remaining_seconds: 0 };
  });
}

export async function getReadiness(): Promise<ReadinessResponse> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/readiness`, { cache: 'no-store' });
    if (!res.ok) {
      throw new Error(`Failed to fetch readiness: ${res.status}`);
    }
    return res.json();
  });
}

export async function getStatusSnapshot(): Promise<any> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/status`, { cache: 'no-store' });
    if (!res.ok) {
      throw new Error(`Failed to fetch status: ${res.status}`);
    }
    return res.json();
  });
}

export async function isFrameAvailable(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/frame/latest?base64=1`, { cache: 'no-store' });
    if (!res.ok) {
      return false;
    }
    const data = await res.json();
    return data?.available === true;
  } catch {
    return false;
  }
}

export async function startWorkloads(target: WorkloadType = 'all'): Promise<StartResponse> {
  const url = `${BASE_URL}/start`;
  console.log('[API] Fetching:', url); // ADD THIS
  
  return safeApiCall(async () => {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        mode: 'cors',
      });
      
      const data = await res.json();

      // 409 with lifecycle=running means the backend is already running.
      // Return it so the caller can reconnect instead of treating it as an error.
      if (res.status === 409 && data?.lifecycle === 'running') {
        return { status: 'running', message: data.error } as StartResponse;
      }

      if (!res.ok) {
        throw new Error(`Failed to start: ${res.status} - ${JSON.stringify(data)}`);
      }
      return data;
    } catch (err) {
      console.error('[API] Fetch error:', err);
      throw err;
    }
  });
}

export async function stopWorkloads(target: WorkloadType = 'all'): Promise<StopResponse> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Failed to stop: ${res.status} - ${errorText}`);
    }
    return await res.json();
  });
}

export async function getPlatformInfo(): Promise<{
  Processor?: string;
  NPU?: string;
  iGPU?: string;
  Memory?: string;
  Storage?: string;
  OS?: string;
}> {
  // console.log('[API] Fetching platform info from:', `${BASE_URL}/platform-info`);
  const response = await fetch(`${BASE_URL}/platform-info`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch platform info: ${response.statusText}`);
  }
  
  const data = await response.json();
  // console.log('[API] Platform info response:', data);
  return data;
}

/**
 * Get system resource metrics (CPU, GPU, memory, power)
 */
export async function getResourceMetrics(): Promise<{
  cpu_utilization: Array<[string, number]>;
  gpu_utilization: Array<[string, ...number[]]>;
  memory: Array<[string, number, number, number, number]>;
  power: Array<[string, ...number[]]>;
  npu_utilization: Array<[string, number]>;
}> {
  // console.log('[API] Fetching metrics from:', `${BASE_URL}/metrics`);

  // Use AbortController to enforce a client-side timeout that's
  // comfortably higher than the backend proxy timeout, so we don't
  // abort aggressively while the metrics service is still responding.
  const controller = new AbortController();
  const timeoutMs = 15000; // 15s client-side timeout
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const response = await fetch(`${BASE_URL}/hardware-metrics`, {
    signal: controller.signal,
  }).catch((err) => {
    clearTimeout(timeoutId);
    console.error('[API] Metrics fetch error:', err);
    throw err;
  });

  clearTimeout(timeoutId);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch resource metrics: ${response.statusText}`);
  }
  
  const data = await response.json();
  // console.log('[API] Metrics response:', data);
  return data;
}

export function getEventsUrl(workloads: WorkloadType[]): string {
  return `${BASE_URL}/events`;
  
  // Example: http://<HOST_IP>:8001/events?workload=rppg&workload=ai-ecg&workload=mdpnp&workload=3d-pose
}

export function getFrameUrl(): string {
  return `${BASE_URL}/video_feed`;
}

// ── Pipeline configuration (set before start) ──────────────────────

export interface PipelineConfig {
  video_file: string | null;
  default_video: string;
  roi: { top: number; left: number; bottom: number; right: number };
  roi_custom: boolean;
  devices: { detect: string; rppg: string; action: string };
  pending?: boolean;
  fallback?: Record<string, { original: string; fallback: string }> | null;
}

export async function getConfig(): Promise<PipelineConfig> {
  const res = await fetch(`${BASE_URL}/config`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Failed to fetch config: ${res.status}`);
  return res.json();
}

export async function uploadVideo(file: File): Promise<{ status: string; video_file: string; size_bytes: number }> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE_URL}/config/video`, { method: 'POST', body: form });
  const contentType = res.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    throw new Error(res.status === 413 ? 'File too large (max 500 MB)' : `Upload failed: server returned ${res.status}`);
  }
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `Upload failed: ${res.status}`);
  return data;
}

export async function clearVideo(): Promise<void> {
  const res = await fetch(`${BASE_URL}/config/video`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Clear video failed: ${res.status}`);
}

export async function setRoi(roi: { top: number; left: number; bottom: number; right: number }): Promise<void> {
  const res = await fetch(`${BASE_URL}/config/roi`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(roi),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `Set ROI failed: ${res.status}`);
}

export async function clearRoi(): Promise<void> {
  const res = await fetch(`${BASE_URL}/config/roi`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Clear ROI failed: ${res.status}`);
}

export async function setDevices(devices: { detect?: string; rppg?: string; action?: string }): Promise<void> {
  const res = await fetch(`${BASE_URL}/config/devices`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(devices),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `Set devices failed: ${res.status}`);
}

export async function getAvailableDevices(): Promise<Record<string, boolean>> {
  const res = await fetch(`${BASE_URL}/config/devices/available`, { cache: 'no-store' });
  if (!res.ok) return { CPU: true, GPU: true, NPU: true }; // assume all available on error
  const data = await res.json();
  return data.devices || { CPU: true, GPU: true, NPU: true };
}

export async function applyConfig(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${BASE_URL}/config/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `Apply failed: ${res.status}`);
  return data;
}

export const api = {
  pingBackend,
  getStreamingStatus,
  getReadiness,
  getStatusSnapshot,
  isFrameAvailable,
  start: startWorkloads,
  stop: stopWorkloads,
  getPlatformInfo,
  getResourceMetrics,
  getEventsUrl,
  getFrameUrl,
  getConfig,
  uploadVideo,
  clearVideo,
  setRoi,
  clearRoi,
  setDevices,
  getAvailableDevices,
  applyConfig,
};

export default api;