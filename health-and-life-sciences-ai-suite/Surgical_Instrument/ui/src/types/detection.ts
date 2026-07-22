// Surgical-Instrument state shape.
// Surgical polyp detection UI state — trimmed to
// a single workload: polyp detection.

export interface PolypDetection {
  detected: boolean;
  count: number;
  confidence: number; // 0–1 — confidence of the most recent detection
  distinct_polyps?: number;          // distinct polyp instances (ByteTrack, filtered by min_track_len)
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
  // Model-only time (GStreamer core `latency` tracer, element-latency for element=det)
  infer_ms?: number;       // mean, last 120 frames
  infer_p50_ms?: number;
  infer_p90_ms?: number;
  infer_p95_ms?: number;
  infer_p99_ms?: number;   // p99,  last 120 frames
  processing_mean_ms?: number;
  processing_p50_ms?: number;
  processing_p90_ms?: number;
  processing_p95_ms?: number;
  processing_p99_ms?: number;
  // Source→sink residence (Intel DLS `latency_tracer`, frame_latency)
  e2e_mean_ms?: number;
  e2e_p50_ms?: number;
  e2e_p90_ms?: number;
  e2e_p95_ms?: number;
  e2e_p99_ms?: number;
  // Legacy aliases (same values as e2e_*) — kept for older API payloads.
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
  polyp: PolypDetection;
  pipelinePerformance: PipelinePerformance;
  modelInfo: ModelInfo | null;
  frameUrl: string | null;
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
