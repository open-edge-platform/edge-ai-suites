// src/services/api.ts

export type WorkloadType = 'rppg' | 'ai-ecg' | 'mdpnp' | '3d-pose' | 'all';
export type StreamingStatus = { locked: boolean; remaining_seconds: number };
export type StartResponse = { 
  status: string; 
  results: Record<string, string>; 
  auto_stop_in_seconds?: number 
};
export type StopResponse = { status: string; message: string };

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';
// Line 13
//const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';

// ADD THIS RIGHT AFTER:
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
  processor?: string;
  npu?: string;
  igpu?: string;
  memory?: string;
  storage?: string;
  os?: string;
}> {
  const response = await fetch(`${BASE_URL}/platform-info`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch platform info: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get system resource metrics (CPU, GPU, memory, power)
 */
export async function getResourceMetrics(): Promise<{
  cpu_utilization: number[];
  gpu_utilization: any[];
  memory: number[];
  power: number[];
}> {
  const response = await fetch(`${BASE_URL}/metrics`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch resource metrics: ${response.statusText}`);
  }
  
  return response.json();
}

export function getEventsUrl(workloads: WorkloadType[]): string {
  const params = workloads.map(w => `workload=${w}`).join('&');
  return `${BASE_URL}/events?${params}`;
  
  // Example: http://10.223.23.206:8001/events?workload=rppg&workload=ai-ecg&workload=mdpnp&workload=3d-pose
}

export const api = {
  pingBackend,
  getStreamingStatus,
  start: startWorkloads,
  stop: stopWorkloads,
  getPlatformInfo,
  getResourceMetrics,
  getEventsUrl,
};

export default api;