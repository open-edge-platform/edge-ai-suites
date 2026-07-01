// src/services/api.ts
export type WorkloadType = 'polyp' | 'all';

export type StartResponse = { status: string; message?: string };
export type StopResponse  = { status: string; message?: string };

export type ReadinessResponse = {
  lifecycle: string;
  ready: boolean;
  checks: Record<string, boolean>;
  errors: Array<{ code: string; message: string }>;
  last_error?: string | null;
};

const BASE_URL = import.meta.env.VITE_API_BASE_URL || `${window.location.origin}/api`;

const HEALTH_TIMEOUT_MS = 10000;

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    p,
    new Promise<T>((_, reject) => setTimeout(() => reject(new Error('timeout')), ms)),
  ]);
}

async function safeApiCall<T>(call: () => Promise<T>): Promise<T> {
  try {
    return await call();
  } catch (e) {
    if (e instanceof TypeError && e.message.includes('fetch')) {
      throw new Error('Backend server is unavailable. Please ensure the aggregator is running.');
    }
    throw e;
  }
}

export async function pingBackend(): Promise<boolean> {
  try {
    const res = await withTimeout(fetch(`${BASE_URL}/health`, { cache: 'no-store' }), HEALTH_TIMEOUT_MS);
    if (!res.ok) return false;
    const data = await res.json();
    return data.status === 'healthy' || data.status === 'ok';
  } catch {
    return false;
  }
}

export async function getStreamingStatus(): Promise<{ locked: boolean; remaining_seconds: number }> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/status`, { cache: 'no-store' });
    if (!res.ok) return { locked: false, remaining_seconds: 0 };
    const data = await res.json();
    const lifecycle = data?.lifecycle;
    return { locked: lifecycle === 'starting' || lifecycle === 'running', remaining_seconds: 0 };
  });
}

export async function getReadiness(): Promise<ReadinessResponse> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/readiness`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`Failed to fetch readiness: ${res.status}`);
    return res.json();
  });
}

export async function getStatusSnapshot(): Promise<any> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/status`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`Failed to fetch status: ${res.status}`);
    return res.json();
  });
}

export async function isFrameAvailable(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/frame/latest?base64=1`, { cache: 'no-store' });
    if (!res.ok) return false;
    const data = await res.json();
    return data?.available === true;
  } catch {
    return false;
  }
}

export async function startWorkloads(_target: WorkloadType = 'all'): Promise<StartResponse> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      mode: 'cors',
    });
    const data = await res.json();
    if (res.status === 409 && data?.lifecycle === 'running') {
      return { status: 'running', message: data.error } as StartResponse;
    }
    if (!res.ok) throw new Error(`Failed to start: ${res.status} - ${JSON.stringify(data)}`);
    return data;
  });
}

export async function stopWorkloads(_target: WorkloadType = 'all'): Promise<StopResponse> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`Failed to stop: ${res.status} - ${t}`);
    }
    return res.json();
  });
}

export async function getPlatformInfo(): Promise<{
  Processor?: string; NPU?: string; iGPU?: string; Memory?: string; Storage?: string; OS?: string;
}> {
  const res = await fetch(`${BASE_URL}/platform-info`);
  if (!res.ok) throw new Error(`Failed to fetch platform info: ${res.statusText}`);
  return res.json();
}

export async function getResourceMetrics(): Promise<{
  cpu_utilization: Array<[string, number]>;
  gpu_utilization: Array<[string, ...number[]]>;
  memory: Array<[string, number, number, number, number]>;
  power: Array<[string, ...number[]]>;
  npu_utilization: Array<[string, number]>;
}> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), 15000);
  const res = await fetch(`${BASE_URL}/hardware-metrics`, { signal: controller.signal })
    .catch((err) => { clearTimeout(id); throw err; });
  clearTimeout(id);
  if (!res.ok) throw new Error(`Failed to fetch resource metrics: ${res.statusText}`);
  return res.json();
}

export function getEventsUrl(_workloads: WorkloadType[]): string {
  return `${BASE_URL}/events`;
}

export function getFrameUrl(): string {
  return `${BASE_URL}/video_feed`;
}

export interface PipelineConfig {
  video_file: string | null;
  default_video: string;
  devices: { detect: string };
  pending?: boolean;
  fallback?: Record<string, { original: string; fallback: string }> | null;
}

export async function getConfig(): Promise<PipelineConfig> {
  const res = await fetch(`${BASE_URL}/config`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Failed to fetch config: ${res.status}`);
  return res.json();
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
};

export default api;
