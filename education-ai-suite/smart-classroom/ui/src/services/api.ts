import { typewriterStream } from '../utils/typewriterStream';
import type { StreamEvent, StreamOptions } from './streamSimulator';
export type ProjectConfig = { name: string; location: string; microphone: string };
export type Settings = { projectName: string; projectLocation: string; microphone: string };
export type SessionMode = 'record' | 'upload';
export type StartSessionRequest = { projectName: string; projectLocation: string; microphone: string; mode: SessionMode };
export type StartSessionResponse = { sessionId: string };

const env = (import.meta as any).env ?? {};
const BASE_URL: string = env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const HEALTH_TIMEOUT_MS = 2000;

let isBackendHealthy = true; // Cache the backend health status

async function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) => setTimeout(() => reject(new Error('timeout')), ms))
  ]);
}

export async function pingBackend(): Promise<boolean> {
  try {
    const res = await withTimeout(fetch(`${BASE_URL}/health`, { cache: 'no-store' }), HEALTH_TIMEOUT_MS);
    if (!res.ok) return false;
    const data = await res.json();
    return data.status === 'ok';
  } catch {
    return false;
  }
}

async function ensureBackendHealth(): Promise<void> {
  if (!isBackendHealthy) {
    const isHealthy = await pingBackend();
    if (!isHealthy) {
      throw new Error('Backend is not healthy. Please try again later.');
    }
    isBackendHealthy = true; // Update the cached status
  }
}

export async function safeApiCall<T>(apiCall: () => Promise<T>): Promise<T> {
  await ensureBackendHealth(); // Ensure backend health before making the API call
  return apiCall();
}

export async function getSettings(): Promise<Settings> {
  return safeApiCall(async() => {
    const res = await fetch(`${BASE_URL}/project`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`Failed to fetch project config: ${res.status}`);
    const cfg = (await res.json()) as ProjectConfig;
    return {
      projectName: cfg.name ?? '',
      projectLocation: cfg.location ?? '',
      microphone: cfg.microphone ?? '',
    };
  });
}

export async function saveSettings(settings: Settings): Promise<ProjectConfig> {
  return safeApiCall(async () =>{
    const payload: ProjectConfig = {
      name: settings.projectName,
      location: settings.projectLocation,
      microphone: settings.microphone,
    };
    const res = await fetch(`${BASE_URL}/project`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Failed to save project config: ${res.status}`);
    return (await res.json()) as ProjectConfig;
  });

}

// Compatibility aliases (use getSettings/saveSettings internally)
export async function getProjectConfig(): Promise<ProjectConfig> {
  return safeApiCall(async () => {
    const s = await getSettings();
    return { name: s.projectName, location: s.projectLocation, microphone: s.microphone };
  });
}

export async function updateProjectConfig(config: ProjectConfig): Promise<ProjectConfig> {
  return safeApiCall(async () => {
    return saveSettings({ projectName: config.name, projectLocation: config.location, microphone: config.microphone });
  });
}


export async function startSession(req: StartSessionRequest): Promise<StartSessionResponse> {
  return safeApiCall(async () => {
  const res = await fetch(`${BASE_URL}/session/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error('Failed to start session');
  return (await res.json()) as StartSessionResponse;});
}

export async function uploadAudio(file: File): Promise<{ filename: string; message: string; path: string }> {
  return safeApiCall(async () => {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE_URL}/upload-audio`, { method: 'POST', body: form });
  if (!res.ok) {
    const json = await res.json();
    throw new Error(json.message || `Upload failed (${res.status})`);
}
return res.json();
});
}

function safeParse(line: string): any | null {
  try { return JSON.parse(line); } catch { return null; }
}
export async function* streamTranscript(audioPath: string, opts: StreamOptions = {}): AsyncGenerator<StreamEvent> {
  await ensureBackendHealth();
  const res = await fetch(`${BASE_URL}/transcribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify({ audio_filename: audioPath }),
    signal: opts.signal,
    cache: 'no-store', // avoid buffering
    keepalive: true,
  });
  if (!res.ok) throw new Error('Failed to start transcription');
  const sessionId = res.headers.get('x-session-id');
  console.log('Received sessionId from header:', sessionId);
  if (opts.onSessionId) opts.onSessionId(sessionId);

  const reader = res.body?.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (reader) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (!line.trim()) continue;
      const chunk = JSON.parse(line);
      for await (const token of typewriterStream(chunk.text, opts.tokenDelayMs ?? 30, opts.signal)) {
        yield { type: 'transcript', token };
      }
    }
  }
  yield { type: 'done' };
}


export async function* streamSummary(sessionId: string, opts: StreamOptions = {}): AsyncGenerator<StreamEvent> {
  await ensureBackendHealth();
  const res = await fetch(`${BASE_URL}/summarize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
    signal: opts.signal,
    cache: 'no-store',
    keepalive: true,
  });
  if (!res.ok) throw new Error(`Failed to start summary: ${res.status} ${res.statusText}`);

  const reader = res.body?.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (reader) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      let chunk: any;
      try { chunk = JSON.parse(trimmed); } catch { continue; }
      const token: string | undefined = chunk.token ?? chunk.summary_token;
      if (typeof token === 'string' && token.length > 0) {
        yield { type: 'summary_token', token };
      }
    }
  }
  yield { type: 'done' };
}



export async function getResourceMetrics(sessionId: string): Promise<any> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/metrics`, {
      method: 'GET',
      headers: { 
        'x-session-id': sessionId, 
        'Accept': 'application/json' 
      }
    });
    
    if (!res.ok) {
      console.warn(`Metrics endpoint returned ${res.status}`);
      return {
        cpu_utilization: [],
        gpu_utilization: [],
        memory: [],
        power: []
      };
    }
    
    const text = await res.text();
    return text ? JSON.parse(text) : {
      cpu_utilization: [],
      gpu_utilization: [],
      memory: [],
      power: []
    };
  });
}

export async function getConfigurationMetrics(sessionId: string): Promise<any> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/performance-metrics`, {
      method: "GET",
      headers: {
        "session_id": sessionId, 
        "Accept": "application/json",
      },
    });

    if (!res.ok) {
      console.warn(`Performance metrics endpoint returned ${res.status}`);
      return {
        configuration: {},
        performance: {},
      };
    }

    const text = await res.text();
    return text ? JSON.parse(text) : { configuration: {}, performance: {} };
  });
}

export async function getPlatformInfo(): Promise<any> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/platform-info`, {
      method: "GET",
      headers: {
        "Accept": "application/json",
      },
    });

    if (!res.ok) {
      console.warn(`Platform info endpoint returned ${res.status}`);
      return {};
    }

    const text = await res.text();
    return text ? JSON.parse(text) : {};
  } );
}