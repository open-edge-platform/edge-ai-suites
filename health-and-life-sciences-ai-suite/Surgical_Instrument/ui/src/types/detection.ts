export interface PipelineLatency {
  mean_ms: number;
  p50_ms: number;
  p90_ms: number;
  p95_ms: number;
  p99_ms: number;
}

export interface PipelineWorkload {
  name: string;
  device: string;          // CPU | GPU | NPU
  status: string;          // running | stopped | error
  fps?: number;
  processing_mean_ms?: number;
  processing_p50_ms?: number;
  processing_p90_ms?: number;
  processing_p95_ms?: number;
  processing_p99_ms?: number;
  latency_ms?: number;
  latency_p99_ms?: number;
}

export interface PipelinePerformance {
  workloads: PipelineWorkload[];
  pipeline_fps: number;
  decode: string;
}

export interface ModelInfo {
  name: string;
  precision: string;
  task: string;
  dataset: string;
  input_source: string;
  model_input: string;
  device: string;
}

export interface DetectionState {
  systemStatus: 'initializing' | 'preparing' | 'ready' | 'starting' | 'running' | 'error' | 'stopping';
  pipelinePerformance: PipelinePerformance;
  pipelineLatency: PipelineLatency;
  modelInfo: ModelInfo | null;
  fps: number;
  uptime: number;          // seconds since inference start
  totalFrames: number;     // running frame counter
  inferP99Ms: number;
  totalP99Ms: number;
  inferP50Ms?: number;
  inferP90Ms?: number;
  inferP95Ms?: number;
  totalP50Ms?: number;
  totalP90Ms?: number;
  totalP95Ms?: number;
}
