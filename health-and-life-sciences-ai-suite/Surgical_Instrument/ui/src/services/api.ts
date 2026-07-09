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
    // If the user has picked a source in the Settings modal, forward it in
    // the body so the pipeline reboots on the correct input. The backend
    // treats an empty body as "use the previously persisted STATE.source".
    const body: Record<string, unknown> = {};
    if (pendingSource) {
      body.source = pendingSource;
    }
    const res = await fetch(`${BASE_URL}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      mode: 'cors',
      body: JSON.stringify(body),
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
  source?: { kind: string; arg: string };
  pending?: boolean;
  fallback?: Record<string, { original: string; fallback: string }> | null;
}

export async function getConfig(): Promise<PipelineConfig> {
  const res = await fetch(`${BASE_URL}/config`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Failed to fetch config: ${res.status}`);
  return res.json();
}

// ---- Videos ---------------------------------------------------------------

export interface VideoItem {
  name: string;
  size_bytes: number;
  mtime: number;
}

export interface VideosListResponse {
  videos: VideoItem[];
  dir: string;
  max_upload_mb: number;
}

export async function listVideos(): Promise<VideosListResponse> {
  const res = await fetch(`${BASE_URL}/videos`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Failed to list videos: ${res.status}`);
  return res.json();
}

export async function uploadVideo(file: File): Promise<{ name: string; size_bytes: number; path: string }> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE_URL}/videos`, { method: 'POST', body: form });
  const data = await res.json().catch(() => ({} as any));
  if (!res.ok) {
    throw new Error(data?.error || `Upload failed: ${res.status}`);
  }
  return data;
}

// ---- Cameras --------------------------------------------------------------

export interface V4L2Camera { device: string; name: string; node: string; }
export interface BaslerCamera { serial: string; model: string; vendor: string; }

export interface CamerasResponse {
  v4l2: V4L2Camera[];
  basler: BaslerCamera[];
  basler_note?: string;
}

export async function listCameras(): Promise<CamerasResponse> {
  const res = await fetch(`${BASE_URL}/devices/cameras`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Failed to list cameras: ${res.status}`);
  return res.json();
}

// ---- Pending source (applied on the next start) --------------------------

export type PipelineSource = { kind: 'file' | 'v4l2' | 'basler'; arg: string };

let pendingSource: PipelineSource | null = null;

export function setPendingSource(src: PipelineSource | null): void {
  pendingSource = src;
}

export function getPendingSource(): PipelineSource | null {
  return pendingSource;
}

export type Device = 'CPU' | 'GPU' | 'NPU';

export async function setDevice(device: Device): Promise<{ status: string; device: string; error?: string }> {
  const res = await fetch(`${BASE_URL}/device`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error || `Failed to set device: ${res.status}`);
  }
  return data;
}

export async function resetSession(): Promise<{ status: string; lifecycle: string; error?: string }> {
  const res = await fetch(`${BASE_URL}/reset`, { method: 'POST' });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error || `Failed to reset: ${res.status}`);
  }
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
  setDevice,
  reset: resetSession,
  listVideos,
  uploadVideo,
  listCameras,
  setPendingSource,
  getPendingSource,
};

export default api;
