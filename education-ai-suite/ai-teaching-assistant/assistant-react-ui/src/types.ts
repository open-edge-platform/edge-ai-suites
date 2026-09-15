// Shared types mirroring the kiosk-core session snapshot and RAG responses.

export interface TtsSegment {
  index: number;
  text: string;
  audio_file: string;
}

export interface SessionSnapshot {
  session_id: string;
  status: string;
  end_reason: string | null;
  error: string | null;
  speech_started: boolean;
  captured_audio_seconds: number;
  transcript: string;
  response: string;
  tts_audio_segments: TtsSegment[];
  tts_errors: string[];
  wakeword?: {
    model: string;
    detected_label: string;
    score: number;
    elapsed_seconds: number;
  };
  performance_metrics?: Record<string, unknown>;
  llm_metrics?: Record<string, unknown>;
}

export interface IngestResponse {
  chunks_added: number;
  source: string;
}

export interface FileIngestResult {
  source: string;
  chunks_added: number;
  status: string;
  detail?: string | null;
  topic?: string | null;
}

export interface BatchIngestResponse {
  total_chunks_added: number;
  files_processed: number;
  files_succeeded: number;
  files_failed: number;
  results: FileIngestResult[];
}

export interface ContextStats {
  collection_name: string;
  document_count: number | null;
  [key: string]: unknown;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  text: string;
}

export type UtilPoint = [string, number];
export type MemoryPoint = [string, number, number, number, number];

export interface SystemMetricsPayload {
  cpu_utilization: UtilPoint[];
  gpu_utilization: UtilPoint[];
  npu_utilization: UtilPoint[];
  memory: MemoryPoint[];
  power: Array<[string, ...number[]]>;
}

export interface PlatformInfo {
  Processor?: string;
  iGPU?: string;
  NPU?: string;
  Memory?: string;
  Storage?: string;
  [key: string]: unknown;
}

export interface ServiceLatency {
  last_ms?: number | null;
  ttft_ms?: number | null;
  tokens_per_sec?: number | null;
  total_tokens?: number | null;
}

export interface ServicePerformancePayload {
  latency?: {
    retrieval?: ServiceLatency;
    llm?: ServiceLatency;
  };
}

export interface SingleLatencyPayload {
  latency?: ServiceLatency;
}

export interface SessionPerfSnapshot {
  ttstMs: number | null;
  endToEndMs: number | null;
  rtf: number | null;
}
