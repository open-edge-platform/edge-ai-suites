// src/services/api.ts
export type WorkloadType = 'rppg' | 'ai-ecg' | 'mdpnp' | '3d-pose' | 'all';
export type StreamingStatus = { locked: boolean; remaining_seconds: number };
export type StartResponse = { 
  status: string; 
  results: Record<string, string>; 
  auto_stop_in_seconds?: number 
};
export type StopResponse = { status: string; message: string };

// Derive API base URL from env or the host the UI is served from
const API_HOST = import.meta.env.VITE_API_HOST || window.location.hostname;
const API_PORT = import.meta.env.VITE_API_PORT || '8001';
const BASE_URL = import.meta.env.VITE_API_BASE_URL || `http://${API_HOST}:${API_PORT}`;
const AGGREGATOR_URL = import.meta.env.VITE_API_BASE_URL || `http://${API_HOST}:${API_PORT}`;
// const METRICS_URL = import.meta.env.VITE_METRICS_BASE_URL || `http://${API_HOST}:${METRICS_PORT}`;

console.log('[API] Aggregator URL:', AGGREGATOR_URL);
// console.log('[API] Metrics URL:', METRICS_URL);

console.log('[API] BASE_URL configured as:', BASE_URL);
console.log('[API] Environment variables:', import.meta.env);
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
    const res = await fetch(`${BASE_URL}/streaming-status`, { cache: 'no-store' });
    if (!res.ok) {
      return { locked: false, remaining_seconds: 0 };
    }
    return await res.json();
  });
}

export async function startWorkloads(target: WorkloadType = 'all'): Promise<StartResponse> {
  const url = `${BASE_URL}/start?target=${target}`;
  console.log('[API] Fetching:', url); // ADD THIS
  
  return safeApiCall(async () => {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        mode: 'cors', // ADD THIS
      });
      
      console.log('[API] Response status:', res.status); // ADD THIS
      console.log('[API] Response ok:', res.ok); // ADD THIS
      
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`Failed to start: ${res.status} - ${errorText}`);
      }
      return await res.json();
    } catch (err) {
      console.error('[API] Fetch error:', err); // ADD THIS
      throw err;
    }
  });
}

export async function stopWorkloads(target: WorkloadType = 'all'): Promise<StopResponse> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/stop?target=${target}`, {
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
  console.log('[API] Fetching platform info from:', `${BASE_URL}/platform-info`);
  const response = await fetch(`${BASE_URL}/platform-info`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch platform info: ${response.statusText}`);
  }
  
  const data = await response.json();
  console.log('[API] Platform info response:', data);
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
  console.log('[API] Fetching metrics from:', `${BASE_URL}/metrics`);
  const response = await fetch(`${BASE_URL}/metrics`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch resource metrics: ${response.statusText}`);
  }
  
  const data = await response.json();
  console.log('[API] Metrics response:', data);
  return data;
}

export async function getWorkloadDevices(): Promise<{
  workloads: {
    rppg?: { env_key: string; configured_device: string; resolved_detail: string };
    ai_ecg?: { env_key: string; configured_device: string; resolved_detail: string };
    mdpnp?: { env_key: string; configured_device: string; resolved_detail: string };
    pose_3d?: { env_key: string; configured_device: string; resolved_detail: string };
  };
}> {
  const response = await fetch(`${BASE_URL}/workload-devices`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch workload devices: ${response.statusText}`);
  }
  
  return response.json();
}


export function getEventsUrl(workloads: WorkloadType[]): string {
  const params = workloads.map(w => `workload=${w}`).join('&');
  return `${BASE_URL}/events?${params}`;
  
  // Example: http://<HOST_IP>:8001/events?workload=rppg&workload=ai-ecg&workload=mdpnp&workload=3d-pose
}

export const api = {
  pingBackend,
  getStreamingStatus,
  start: startWorkloads,
  stop: stopWorkloads,
  getPlatformInfo,
  getResourceMetrics,
  getWorkloadDevices,  
  getEventsUrl,
};

export default api;