// Surgical-Instrument state shape.
// Mirrors NICU-Warmer's NicuState surface for layout reuse, but trimmed to
// a single workload: polyp detection.

export interface PolypDetection {
  detected: boolean;
  count: number;
  confidence: number; // 0–1 — confidence of the most recent detection
}

export interface PipelineWorkload {
  name: string;
  device: string;          // CPU | GPU | NPU
  status: string;          // running | stopped | error
  fps?: number;
  latency_ms?: number;
  latency_p99_ms?: number;
}

export interface PipelinePerformance {
  workloads: PipelineWorkload[];
  pipeline_fps: number;
  decode: string;
}

export interface NicuState {
  systemStatus: 'initializing' | 'preparing' | 'ready' | 'starting' | 'running' | 'error' | 'stopping';
  polyp: PolypDetection;
  pipelinePerformance: PipelinePerformance;
  frameUrl: string | null;
  fps: number;
  uptime: number; // seconds
}
