// Surgical-Instrument state shape.
// Surgical polyp detection UI state — trimmed to
// a single workload: polyp detection.

export interface PolypDetection {
  detected: boolean;
  count: number;
  confidence: number; // 0–1 — confidence of the most recent detection
  frames_processed?: number;         // frames the model ran on this session
  frames_with_detection?: number;    // frames where at least one polyp was found
  detection_rate?: number;           // frames_with_detection / frames_processed, in [0,1]
  peak_confidence?: number;          // highest confidence seen this session, 0..1
  session_seconds?: number;          // wall time since Start
}

export interface PipelineWorkload {
  name: string;
  device: string;          // CPU | GPU | NPU
  status: string;          // running | stopped | error
  fps?: number;
  infer_ms?: number;       // inference-only mean latency
  latency_ms?: number;     // end-to-end mean latency
  latency_p99_ms?: number; // end-to-end p99 (real, computed from last 120 samples)
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
  polyp: PolypDetection;
  pipelinePerformance: PipelinePerformance;
  modelInfo: ModelInfo | null;
  frameUrl: string | null;
  fps: number;
  uptime: number;          // seconds since inference start
  totalFrames: number;     // running frame counter
  inferP99Ms: number;
  totalP99Ms: number;
}
