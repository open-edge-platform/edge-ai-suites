import { typewriterStream } from '../utils/typewriterStream';
import type { StreamEvent, StreamOptions } from './streamSimulator';

export type ProjectConfig = { 
  name: string; 
  location: string; 
  microphone: string; 
  frontCamera?: string; 
  backCamera?: string; 
  boardCamera?: string 
};

export type Settings = { 
  projectName: string; 
  projectLocation: string; 
  microphone: string; 
  frontCamera?: string; 
  backCamera?: string; 
  boardCamera?: string 
};

export type SessionMode = 'record' | 'upload';
export type StartSessionRequest = { projectName: string; projectLocation: string; microphone: string; mode: SessionMode };
export type StartSessionResponse = { sessionId: string };

const env = (import.meta as any).env ?? {};
const BASE_URL: string = env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const HEALTH_TIMEOUT_MS = 10000;

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

export async function safeApiCall<T>(apiCall: () => Promise<T>): Promise<T> {
  try {
    return await apiCall();
  } catch (error) {
    // Check if it's a network error or backend unavailable
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error('Backend server is unavailable. Please ensure the backend is running.');
    }
    throw error;
  }
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
      frontCamera: cfg.frontCamera || '', // Empty string as default
      backCamera: cfg.backCamera || '',   // Empty string as default
      boardCamera: cfg.boardCamera || ''  // Empty string as default
    };
  });
}

export async function saveSettings(settings: Settings): Promise<ProjectConfig> {
  return safeApiCall(async () =>{
    const payload: ProjectConfig = {
      name: settings.projectName,
      location: settings.projectLocation,
      microphone: settings.microphone,
      frontCamera: settings.frontCamera,
      backCamera: settings.backCamera,
      boardCamera: settings.boardCamera
    };
    console.log('Sending payload to /project:', payload);
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

export async function* streamTranscript(
  audioPath: string,
  opts: StreamOptions = {}
): AsyncGenerator<StreamEvent> {
 
  // Prepare request body based on whether it's microphone or file
  const requestBody =
    audioPath === "MICROPHONE" || audioPath === ""
      ? {
          audio_filename: "",
          source_type: "microphone",
        }
      : {
          audio_filename: audioPath,
          source_type: "audio_file",
        };
 
  console.log("Sending transcription request:", requestBody);
 
  const res = await fetch(`${BASE_URL}/transcribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(requestBody),
    signal: opts.signal,
    cache: "no-store",
    keepalive: true,
  });
 
  if (!res.ok) {
    const errorText = await res.text();
    console.error("Transcription request failed:", errorText);
    throw new Error(`Failed to start transcription: ${res.status} - ${errorText}`);
  }
  const sessionId = res.headers.get("x-session-id");
  console.log("Received sessionId from header:", sessionId);
  if (opts.onSessionId) opts.onSessionId(sessionId);
  const reader = res.body?.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (reader) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let lines = buffer.split("\n");
    buffer = lines.pop() || "";
 
    for (const line of lines) {
      if (!line.trim()) continue;
 
      const chunk = JSON.parse(line);
      const text = chunk.text || "";
      for await (const token of typewriterStream(
        text,
        opts.tokenDelayMs ?? 0,   
        opts.signal
      )) {
        yield { type: "transcript", token };
      }
    }
  }
 
  yield { type: "done" };
}

export async function* streamSummary(sessionId: string, opts: StreamOptions = {}): AsyncGenerator<StreamEvent> {
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

export async function fetchMindmap(sessionId: string): Promise<string> {
  const response = await fetch(`${BASE_URL}/mindmap`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(errText || `HTTP ${response.status}`);
  }

  const data: { mindmap?: string; error?: string } = await response.json();

  if (data.error) {
    throw new Error(data.error);
  }

  if (!data.mindmap) {
    throw new Error("No mindmap field returned from server.");
  }

  return data.mindmap;
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

// Updated video analytics functions to match backend API structure
export const startVideoAnalytics = async (
  requests: Array<{
    pipeline_name: string;
    source: string;
  }>,
  sessionId: string
): Promise<any> => {
  return safeApiCall(async () => {
    const response = await fetch(`${BASE_URL}/start-video-analytics-pipeline`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': sessionId,
      },
      body: JSON.stringify(requests),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `Failed to start video analytics: ${response.status}`);
    }

    return response.json();
  });
};

export const stopVideoAnalytics = async (
  requests: Array<{
    pipeline_name: string;
    source?: string;
  }>,
  sessionId: string
): Promise<any> => {
  return safeApiCall(async () => {
    const response = await fetch(`${BASE_URL}/stop-video-analytics-pipeline`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': sessionId,
      },
      body: JSON.stringify(requests),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `Failed to stop video analytics: ${response.status}`);
    }

    return response.json();
  });
};

// Backward compatibility aliases
export const startVideoAnalyticsPipeline = startVideoAnalytics;

export async function getClassStatistics(sessionId: string): Promise<{
  student_count: number;
  stand_count: number;
  raise_up_count: number;
  stand_reid: { student_id: number; count: number }[];
}> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/class-statistics`, {
      method: 'GET',
      headers: {
        'x-session-id': sessionId,
        'Accept': 'application/json',
      },
    });

    if (!res.ok) {
      console.warn(`Class statistics endpoint returned ${res.status}`);
      return {
        student_count: 0,
        stand_count: 0,
        raise_up_count: 0,
        stand_reid: [],
      };
    }

    const text = await res.text();
    return text
      ? JSON.parse(text)
      : {
          student_count: 0,
          stand_count: 0,
          raise_up_count: 0,
          stand_reid: [],
        };
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

export async function getAudioDevices(): Promise<string[]> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/devices`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`Failed to fetch audio devices: ${res.status}`);
    const data = await res.json();
    return data.devices || [];
  });
}

export async function stopMicrophone(sessionId: string): Promise<{ status: string; message: string }> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/stop-mic?session_id=${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) throw new Error(`Failed to stop microphone: ${res.status}`);
    return await res.json();
  });
}

export async function startMicrophone(): Promise<{ status: string; message: string; sessionId?: string }> {
  const res = await fetch(`${BASE_URL}/transcribe`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
      "x-source-type": "microphone"
    },
    body: JSON.stringify({
      audio_filename: "",
      source_type: "microphone"
    }),
    cache: "no-store",
    keepalive: true,
  });

  if (!res.ok) {
    const errorText = await res.text();
    console.error("❌ Failed to start microphone:", errorText);
    throw new Error(`Failed to start microphone: ${res.status}`);
  }

  // ✅ Extract X-Session-ID from headers
  const sessionId = res.headers.get("x-session-id") || undefined;
  if (sessionId) {
    localStorage.setItem("sessionId", sessionId);
    console.log("🟢 Session ID saved:", sessionId);
  }

  // ✅ Stream-safe handling: just confirm first chunk
  const reader = res.body?.getReader();
  const decoder = new TextDecoder();
  let firstChunk = "";

  if (reader) {
    const { value, done } = await reader.read();
    if (!done && value) {
      firstChunk = decoder.decode(value, { stream: true });
      console.log("🎙️ Microphone stream started:", firstChunk.slice(0, 100)); // preview only
    }
  }

  // ✅ Clean up reader to avoid hanging
  reader?.cancel();

  return {
    status: "recording",
    message: "Microphone streaming started successfully.",
    sessionId
  };
}