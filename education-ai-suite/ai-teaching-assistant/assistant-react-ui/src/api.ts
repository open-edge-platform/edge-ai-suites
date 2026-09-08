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
    const raw = await res.text();
    if (raw) {
      try {
        const body = JSON.parse(raw);
        detail = body.detail ?? body.error?.message ?? JSON.stringify(body);
      } catch {
        detail = raw;
      }
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

// ── kiosk-core session API ──────────────────────────────────────────────────

export interface CaptureModeInfo {
  host_mic_available: boolean;
  recommended: "host" | "browser";
  host_devices: { id: number; name: string; default_samplerate: number }[];
}

export async function getCaptureMode(): Promise<CaptureModeInfo> {
  return asJson<CaptureModeInfo>(await fetch(`${API.kiosk}/api/v1/capture-mode`));
}

/** Encode a UI-selected device for the host-capture endpoints. Browser
 * MediaDevices IDs are opaque hashes that do not map to host `sounddevice`
 * identifiers, so only numeric indices or human-readable names are forwarded;
 * anything else is dropped so kiosk-core uses its default host input device. */
function hostDevicePayload(device: string | undefined): number | string | undefined {
  if (!device) return undefined;
  const maybeNumber = Number(device);
  if (Number.isFinite(maybeNumber)) return maybeNumber;
  const looksOpaqueBrowserId = /^[a-f0-9]{32,}$/i.test(device);
  return looksOpaqueBrowserId ? undefined : device;
}

export async function startHostSession(
  sampleRate: number,
  history: { role: string; content: string }[],
  opts: {
    chunkSeconds: number;
    silenceTimeoutSeconds: number;
    maxSessionSeconds: number;
    silenceThreshold: number;
    device?: string;
  }
): Promise<SessionSnapshot> {
  const payload: Record<string, unknown> = {
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
  };
  const device = hostDevicePayload(opts.device);
  if (device !== undefined) payload.device = device;
  const res = await fetch(`${API.kiosk}/api/v1/sessions/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return asJson<SessionSnapshot>(res);
}

export async function stopHostSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API.kiosk}/api/v1/sessions/${sessionId}/stop`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`stop session failed: HTTP ${res.status}`);
}

export async function startTextQuery(
  text: string,
  history: { role: string; content: string }[]
): Promise<SessionSnapshot> {
  const res = await fetch(`${API.kiosk}/api/v1/query/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      language: "en",
      temperature: 0.0,
      history,
      include_performance_metrics: true,
      include_llm_metrics: true,
    }),
  });
  return asJson<SessionSnapshot>(res);
}

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

export async function startSessionAfterWakeword(
  sampleRate: number,
  history: { role: string; content: string }[],
  opts: {
    chunkSeconds: number;
    silenceTimeoutSeconds: number;
    maxSessionSeconds: number;
    silenceThreshold: number;
    wakewordModel: string;
    wakewordThreshold: number;
    wakewordVadThreshold: number;
    wakewordPatienceFrames: number;
    wakewordTimeoutSeconds: number;
    wakewordInferenceFramework: string;
    device?: string;
  }
): Promise<SessionSnapshot> {
  const payload: Record<string, unknown> = {
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
    wakeword_model: opts.wakewordModel,
    wakeword_threshold: opts.wakewordThreshold,
    wakeword_vad_threshold: opts.wakewordVadThreshold,
    wakeword_patience_frames: opts.wakewordPatienceFrames,
    wakeword_timeout_seconds: opts.wakewordTimeoutSeconds,
    wakeword_inference_framework: opts.wakewordInferenceFramework,
  };
  if (opts.device) {
    const maybeNumber = Number(opts.device);
    if (Number.isFinite(maybeNumber)) {
      payload.device = maybeNumber;
    } else {
      // Browser MediaDevices IDs are opaque hashes and do not map to host
      // sounddevice identifiers. Only forward human-readable names.
      const looksOpaqueBrowserId = /^[a-f0-9]{32,}$/i.test(opts.device);
      if (!looksOpaqueBrowserId) {
        payload.device = opts.device;
      }
    }
  }
  const res = await fetch(`${API.kiosk}/api/v1/sessions/start-after-wakeword`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return asJson<SessionSnapshot>(res);
}

export async function startBrowserWakewordSession(opts: {
  sampleRate: number;
  wakewordModel: string;
  wakewordThreshold: number;
  wakewordVadThreshold: number;
  wakewordPatienceFrames: number;
  wakewordInferenceFramework: string;
}): Promise<{ wakeword_session_id: string; status: string }> {
  const res = await fetch(`${API.kiosk}/api/v1/wakeword/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sample_rate: opts.sampleRate,
      wakeword_model: opts.wakewordModel,
      wakeword_threshold: opts.wakewordThreshold,
      wakeword_vad_threshold: opts.wakewordVadThreshold,
      wakeword_patience_frames: opts.wakewordPatienceFrames,
      wakeword_inference_framework: opts.wakewordInferenceFramework,
    }),
  });
  return asJson<{ wakeword_session_id: string; status: string }>(res);
}

export async function pushBrowserWakewordAudio(
  wakewordSessionId: string,
  wav: ArrayBuffer
): Promise<{ wakeword_session_id: string; detected: boolean; score: number; detected_label?: string | null }> {
  const res = await fetch(`${API.kiosk}/api/v1/wakeword/${wakewordSessionId}/audio`, {
    method: "POST",
    headers: { "Content-Type": "audio/wav" },
    body: wav,
  });
  return asJson<{ wakeword_session_id: string; detected: boolean; score: number; detected_label?: string | null }>(res);
}

export async function stopBrowserWakewordSession(
  wakewordSessionId: string
): Promise<{ wakeword_session_id: string; status: string }> {
  const res = await fetch(`${API.kiosk}/api/v1/wakeword/${wakewordSessionId}/stop`, {
    method: "POST",
  });
  return asJson<{ wakeword_session_id: string; status: string }>(res);
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
    form.append("file", file, file.name);
  }
  const res = await fetch(`${API.rag}/api/v1/context/file`, {
    method: "POST",
    body: form,
  });
  return asJson<BatchIngestResponse>(res);
}

export async function clearContext(): Promise<void> {
  const res = await fetch(`${API.rag}/api/v1/context`, { method: "DELETE" });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    const raw = await res.text();
    if (raw) {
      try {
        const body = JSON.parse(raw);
        detail = body.detail ?? body.error?.message ?? JSON.stringify(body);
      } catch {
        detail = raw;
      }
    }
    throw new Error(`Failed to clear context: ${detail}`);
  }
}

export async function getContextStats(): Promise<ContextStats> {
  return asJson<ContextStats>(await fetch(`${API.rag}/api/v1/context/stats`));
}
