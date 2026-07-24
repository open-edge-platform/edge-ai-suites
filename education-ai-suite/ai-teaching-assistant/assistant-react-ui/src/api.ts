import { API } from "./config";
import type {
  BatchIngestResponse,
  ContextStats,
  PlatformInfo,
  ServicePerformancePayload,
  SessionSnapshot,
  SingleLatencyPayload,
  SystemMetricsPayload,
} from "./types";

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? body.error?.message ?? JSON.stringify(body);
    } catch {
      detail = (await res.text()) || detail;
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

// ── kiosk-core session API ──────────────────────────────────────────────────

export async function startStreamSession(
  sampleRate: number,
  history: { role: string; content: string }[],
  opts: {
    chunkSeconds: number;
    silenceTimeoutSeconds: number;
    maxSessionSeconds: number;
    silenceThreshold: number;
  }
): Promise<SessionSnapshot> {
  const res = await fetch(`${API.kiosk}/api/v1/sessions/start-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sample_rate: sampleRate,
      chunk_seconds: opts.chunkSeconds,
      silence_timeout_seconds: opts.silenceTimeoutSeconds,
      max_session_seconds: opts.maxSessionSeconds,
      silence_threshold: opts.silenceThreshold,
      language: "en",
      temperature: 0.0,
      tts_model: "speecht5",
      tts_language: "English",
      history,
      include_performance_metrics: true,
      include_llm_metrics: true,
    }),
  });
  return asJson<SessionSnapshot>(res);
}

export async function pushAudioChunk(sessionId: string, wav: ArrayBuffer): Promise<void> {
  const res = await fetch(`${API.kiosk}/api/v1/sessions/${sessionId}/audio`, {
    method: "POST",
    headers: { "Content-Type": "audio/wav" },
    body: wav,
  });
  if (!res.ok) throw new Error(`push chunk failed: HTTP ${res.status}`);
}

export async function endAudioStream(sessionId: string): Promise<void> {
  const res = await fetch(`${API.kiosk}/api/v1/sessions/${sessionId}/audio/end`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`end stream failed: HTTP ${res.status}`);
}

export async function getSession(sessionId: string): Promise<SessionSnapshot> {
  return asJson<SessionSnapshot>(await fetch(`${API.kiosk}/api/v1/sessions/${sessionId}`));
}

export async function getSystemMetrics(): Promise<SystemMetricsPayload> {
  return asJson<SystemMetricsPayload>(await fetch(`${API.kiosk}/api/v1/metrics`));
}

export async function getPlatformInfo(): Promise<PlatformInfo> {
  return asJson<PlatformInfo>(await fetch(`${API.kiosk}/api/v1/platform-info`));
}

export async function getRagPerformance(): Promise<ServicePerformancePayload> {
  return asJson<ServicePerformancePayload>(await fetch(`${API.rag}/api/v1/performance`));
}

export async function getTtsPerformance(): Promise<SingleLatencyPayload> {
  return asJson<SingleLatencyPayload>(await fetch(`${API.tts}/v1/performance`));
}

export async function getAsrPerformance(): Promise<SingleLatencyPayload> {
  return asJson<SingleLatencyPayload>(await fetch(`${API.analyzer}/v1/performance`));
}

export function responseAudioUrl(sessionId: string, index: number): string {
  return `${API.kiosk}/api/v1/sessions/${sessionId}/response-audio/${index}`;
}

// ── rag-service ingestion API ───────────────────────────────────────────────

export async function ingestFiles(files: File[]): Promise<BatchIngestResponse> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file, file.name);
  }
  const res = await fetch(`${API.rag}/api/v1/context/file`, {
    method: "POST",
    body: form,
  });
  return asJson<BatchIngestResponse>(res);
}

export async function clearContext(): Promise<void> {
  await fetch(`${API.rag}/api/v1/context`, { method: "DELETE" });
}

export async function getContextStats(): Promise<ContextStats> {
  return asJson<ContextStats>(await fetch(`${API.rag}/api/v1/context/stats`));
}
