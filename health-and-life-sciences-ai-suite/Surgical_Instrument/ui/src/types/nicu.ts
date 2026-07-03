// Surgical-Instrument state shape.
// Mirrors NICU-Warmer's NicuState surface for layout reuse, but trimmed to
// a single workload: polyp detection.

export interface PolypDetection {
  detected: boolean;
  count: number;
  confidence: number; // 0–1 — confidence of the most recent detection
  cumulative_detections?: number;    // sum of all polyps across every frame this session
  frames_with_detection?: number;    // number of frames where at least one polyp was found
  detection_rate?: number;           // frames_with_detection / total_frames, in [0,1]
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

export interface NicuState {
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
