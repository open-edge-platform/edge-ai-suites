/**
 * API Service for Health & Life Sciences AI Suite
 * Type-safe wrapper around aggregator service endpoints
 */

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = import.meta.env.VITE_AGGREGATOR_URL?.replace('/events', '') || 'http://localhost:8001';

const TIMEOUT_MS = 5000; // 5 seconds timeout for API calls

// ============================================================================
// TypeScript Interfaces
// ============================================================================

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  service: string;
  version: string;
  timestamp: number;
  workload_type: string;
  grpc_port: number;
  http_port: number;
}

export interface StreamingStatus {
  locked: boolean;
  remaining_seconds: number;
}

export interface WorkloadResult {
  [workloadName: string]: string; // e.g., { "dds-bridge": "200: OK", "ai-ecg": "started" }
}

export interface StartResponse {
  status: 'ok' | 'locked';
  results?: WorkloadResult;
  auto_stop_in_seconds?: number;
  remaining_seconds?: number;
}

export interface StopResponse {
  status: 'ok';
  results: WorkloadResult;
}

export interface PlatformInfo {
  cpu: {
    model: string;
    cores: number;
    usage: number;
  };
  memory: {
    total: number;
    used: number;
    available: number;
  };
  gpu?: {
    model: string;
    driver: string;
  };
  [key: string]: any; // Allow additional fields from backend
}

export interface Metrics {
  [key: string]: number | string; // Flexible metrics structure from backend
}

export interface RootEndpoint {
  service: string;
  version: string;
  workload_type: string;
  endpoints: string[];
}

// ============================================================================
// Error Handling Utilities
// ============================================================================

/**
 * Add timeout to any promise
 */
async function withTimeout<T>(promise: Promise<T>, timeoutMs: number = TIMEOUT_MS): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error('Request timeout')), timeoutMs)
    ),
  ]);
}

/**
 * Safe API call wrapper with automatic error handling
 * Provides consistent error messages across all API calls
 */
async function safeApiCall<T>(apiCall: () => Promise<T>): Promise<T> {
  try {
    return await apiCall();
  } catch (error) {
    // Network error (backend unavailable)
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error('Aggregator service is unavailable. Please ensure it is running.');
    }

    // Timeout error
    if (error instanceof Error && error.message === 'Request timeout') {
      throw new Error('Request timed out. The aggregator service may be overloaded.');
    }

    // Re-throw with context
    if (error instanceof Error) {
      throw new Error(`API Error: ${error.message}`);
    }

    throw new Error('Unknown API error occurred');
  }
}

/**
 * Parse JSON response with error handling
 */
async function parseJson<T>(response: Response): Promise<T> {
  // Handle HTTP errors
  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown error');
    throw new Error(`HTTP ${response.status}: ${errorText}`);
  }

  // Parse JSON
  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new Error('Failed to parse JSON response from server');
  }
}

// ============================================================================
// API Methods
// ============================================================================

export const api = {
  // --------------------------------------------------------------------------
  // Health & Status Endpoints
  // --------------------------------------------------------------------------

  /**
   * Check aggregator service health
   * GET /health
   */
  health: async (): Promise<HealthStatus> => {
    return safeApiCall(async () => {
      const response = await withTimeout(
        fetch(`${BASE_URL}/health`, {
          method: 'GET',
          cache: 'no-store',
        })
      );
      return parseJson<HealthStatus>(response);
    });
  },

  /**
   * Get root endpoint information
   * GET /
   */
  root: async (): Promise<RootEndpoint> => {
    return safeApiCall(async () => {
      const response = await withTimeout(
        fetch(`${BASE_URL}/`, {
          method: 'GET',
          cache: 'no-store',
        })
      );
      return parseJson<RootEndpoint>(response);
    });
  },

  /**
   * Get streaming lock status (whether UI should disable Start button)
   * GET /streaming-status
   * 
   * Returns:
   *   - locked: true if streaming window is active (60s auto-stop timer running)
   *   - remaining_seconds: seconds until auto-stop occurs
   */
  streamingStatus: async (): Promise<StreamingStatus> => {
    return safeApiCall(async () => {
      const response = await withTimeout(
        fetch(`${BASE_URL}/streaming-status`, {
          method: 'GET',
          cache: 'no-store',
        })
      );
      return parseJson<StreamingStatus>(response);
    });
  },

  // --------------------------------------------------------------------------
  // Workload Control Endpoints
  // --------------------------------------------------------------------------

  /**
   * Start workloads
   * POST /start?target={workload}
   * 
   * Target options:
   *   - "all" (default) - Start all workloads
   *   - "mdpnp" - Start MDPNP/DDS-Bridge only
   *   - "ai-ecg" - Start AI-ECG only
   *   - "3d-pose" - Start 3D Pose only
   *   - "rppg" - Start RPPG only
   *   - "mdpnp,ai-ecg" - Start multiple (comma-separated)
   * 
   * Creates a 60-second streaming window. During this time:
   *   - /streaming-status returns locked=true
   *   - Workloads auto-stop after 60 seconds
   *   - Additional /start calls are rejected
   */
  start: async (target: string = 'all'): Promise<StartResponse> => {
    return safeApiCall(async () => {
      const response = await withTimeout(
        fetch(`${BASE_URL}/start?target=${encodeURIComponent(target)}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
        }),
        10000 // 10 seconds for start (may take longer)
      );
      return parseJson<StartResponse>(response);
    });
  },

  /**
   * Stop workloads
   * POST /stop?target={workload}
   * 
   * Target options: same as /start
   * 
   * Manually stops workloads and clears the streaming lock.
   * This allows the UI to immediately start a new session.
   */
  stop: async (target: string = 'all'): Promise<StopResponse> => {
    return safeApiCall(async () => {
      const response = await withTimeout(
        fetch(`${BASE_URL}/stop?target=${encodeURIComponent(target)}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
        }),
        10000 // 10 seconds for stop
      );
      return parseJson<StopResponse>(response);
    });
  },

  // --------------------------------------------------------------------------
  // Metrics & Platform Info Endpoints
  // --------------------------------------------------------------------------

  /**
   * Get system metrics (for System Metrics accordion)
   * GET /metrics
   * 
   * Proxied from metrics-service (port 9000)
   */

  /**
   * Get platform information (for Platform Info accordion)
   * GET /platform-info
   * 
   * Proxied from metrics-service (port 9000)
   */
  // export async function getResourceMetrics(sessionId: string): Promise<any> {
  //   return safeApiCall(async () => {
  //     const res = await fetch(`${BASE_URL}/metrics`, {
  //       method: 'GET',
  //       headers: { 
  //         'x-session-id': sessionId, 
  //         'Accept': 'application/json' 
  //       }
  //     });
      
  //     if (!res.ok) {
  //       console.warn(`Metrics endpoint returned ${res.status}`);
  //       return {
  //         cpu_utilization: [],
  //         gpu_utilization: [],
  //         npu_utilization: [],
  //         memory: [],
  //         power: []
  //       };
  //     }
      
  //     const text = await res.text();
  //     return text ? JSON.parse(text) : {
  //       cpu_utilization: [],
  //       gpu_utilization: [],
  //       npu_utilization: [],
  //       memory: [],
  //       power: []
  //     };
  //   });
  // }
  
  // export async function getConfigurationMetrics(sessionId: string): Promise<any> {
  //   return safeApiCall(async () => {
  //     const res = await fetch(`${BASE_URL}/performance-metrics`, {
  //       method: "GET",
  //       headers: {
  //         "session_id": sessionId, 
  //         "Accept": "application/json",
  //       },
  //     });
  
  //     if (!res.ok) {
  //       console.warn(`Performance metrics endpoint returned ${res.status}`);
  //       return {
  //         configuration: {},
  //         performance: {},
  //       };
  //     }
  
  //     const text = await res.text();
  //     return text ? JSON.parse(text) : { configuration: {}, performance: {} };
  //   });
  // }
  

  // --------------------------------------------------------------------------
  // SSE Events Endpoint (handled by sseMiddleware in Redux)
  // --------------------------------------------------------------------------

  /**
   * Get SSE event stream URL
   * GET /events?workloads={filter}
   * 
   * This is not called directly - it's used by Redux sseMiddleware
   * 
   * Query params:
   *   - workloads: Optional comma-separated filter (e.g., "rppg,ai-ecg")
   *   - If omitted, all workload events are sent
   */
  getEventsUrl: (workloads?: string[]): string => {
    const base = `${BASE_URL}/events`;
    if (workloads && workloads.length > 0) {
      return `${base}?workloads=${workloads.join(',')}`;
    }
    return base;
  },
};

// ============================================================================
// Convenience Functions (for backward compatibility)
// ============================================================================

/**
 * Ping aggregator service to check availability
 */
export async function pingBackend(): Promise<boolean> {
  try {
    const response = await withTimeout(fetch(`${BASE_URL}/health`, { cache: 'no-store' }), 3000);
    if (!response.ok) return false;
    const data = await response.json();
    return data.status === 'healthy';
  } catch {
    return false;
  }
}

/**
 * Start all workloads (convenience wrapper)
 */
export async function startAllWorkloads(): Promise<StartResponse> {
  return api.start('all');
}

/**
 * Stop all workloads (convenience wrapper)
 */
export async function stopAllWorkloads(): Promise<StopResponse> {
  return api.stop('all');
}

// ============================================================================
// Export as default for convenient imports
// ============================================================================

export default api;