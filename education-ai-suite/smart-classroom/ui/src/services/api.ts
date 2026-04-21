import type { StreamEvent, StreamOptions } from './streamSimulator';
import { store } from "../redux/store";
import { 
  setVideoStatus,
  setVideoAnalyticsActive,
  setVideoPlaybackMode
} from "../redux/slices/uiSlice";
import type { CsSearchParams, CsSearchResult } from "../components/LeftPanel/ResultSection";

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

export interface SearchRequest {
  session_id: string;
  query: string;
  top_k?: number;
}

export interface SearchResult {
  session_id: string;
  query: string;
  results: any[];
}

const env = (import.meta as any).env ?? {};
const BASE_URL: string = env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
// Default to empty string (same-origin) so the Vite dev proxy routes /api/v1
// to port 9011 without CORS. Set VITE_CONTENT_SEARCH_API_URL for remote hosts.
const CONTENT_SEARCH_API_URL: string = env.VITE_CONTENT_SEARCH_API_URL || '';
const HEALTH_TIMEOUT_MS = 5000;

async function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) => setTimeout(() => reject(new Error('timeout')), ms))
  ]);
}

export async function startPipelineMonitoring(sessionId: string) {
  const controller = new AbortController();
  try {
    for await (const event of monitorVideoAnalyticsPipelines(
      sessionId,
      controller.signal
    )) {
      if (!event?.pipelines) continue;
      let anyRunning = false;
      let allCompleted = true;

      for (const pipeline of event.pipelines) {

        if (pipeline.status === "running") {
          anyRunning = true;
        }

        if (
          pipeline.status !== "completed" &&
          pipeline.status !== "stopped"
        ) {
          allCompleted = false;
        }
      }

      if (anyRunning) {
        store.dispatch(setVideoAnalyticsActive(true));
        store.dispatch(setVideoStatus("streaming"));
        store.dispatch(setVideoPlaybackMode(false));
      }

      if (allCompleted && !anyRunning) {
        console.log("✅ All pipelines completed");
        store.dispatch(setVideoAnalyticsActive(false));
        store.dispatch(setVideoStatus("completed"));
        store.dispatch(setVideoPlaybackMode(true));
        break;
      }
    }

  }
  catch (err) {
    console.error("Monitor error:", err);
  }
  return controller;
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
      frontCamera: cfg.frontCamera || '', 
      backCamera: cfg.backCamera || '',   
      boardCamera: cfg.boardCamera || ''  
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

export async function storeAudioDuration(sessionId: string, audioFile: File): Promise<{ status: string; message: string }> {
  return safeApiCall(async () => {
    console.log(`🔊 Extracting audio duration from ${audioFile.name}...`);
    const duration = await getAudioDuration(audioFile);
    
    if (!duration) {
      throw new Error('Could not extract audio duration from file');
    }

    console.log(`📤 Sending audio duration to backend: ${duration.toFixed(2)}s`);
    const response = await fetch(`${BASE_URL}/store-audio-duration`, {
      method: 'POST',
      headers: {
        'X-Session-ID': sessionId,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ duration }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Audio metadata upload failed: ${response.status} - ${errorText}`);
    }

    const result = await response.json();
    console.log('✅ Audio duration stored at backend:', result);
    return result;
  });
}

/**
 * Extract audio duration using HTML5 Audio API
 * This is more reliable than ffprobe and works in the browser
 */
export function getAudioDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    try {
      const audio = document.createElement('audio');
      const url = URL.createObjectURL(file);
      
      // Set a timeout in case metadata never loads
      const timeout = setTimeout(() => {
        URL.revokeObjectURL(url);
        console.warn('Audio duration extraction timed out');
        resolve(null);
      }, 10000); // 10 second timeout

      audio.addEventListener('loadedmetadata', () => {
        clearTimeout(timeout);
        URL.revokeObjectURL(url);
        const duration = audio.duration;
        console.log(`✅ Extracted audio duration: ${duration.toFixed(2)}s`);
        resolve(isFinite(duration) ? duration : null);
      }, { once: true });

      audio.addEventListener('error', () => {
        clearTimeout(timeout);
        URL.revokeObjectURL(url);
        console.warn('Error loading audio metadata');
        resolve(null);
      }, { once: true });

      // Trigger metadata loading
      audio.src = url;
      audio.load();
    } catch (error) {
      console.error('Error extracting audio duration:', error);
      resolve(null);
    }
  });
}

export async function* streamTranscript(
  audioPath: string,
  sessionId: string,
  opts: StreamOptions = {}
): AsyncGenerator<StreamEvent> {
  const requestBody =
    audioPath === "MICROPHONE" || audioPath === ""
      ? { audio_filename: "", source_type: "microphone" }
      : { audio_filename: audioPath, source_type: "audio_file" };

  let res: Response;

  try {
    res = await fetch(`${BASE_URL}/transcribe`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-session-id": sessionId
      },
      body: JSON.stringify(requestBody),
      signal: opts.signal,
      cache: "no-store"
    });
  } catch (err) {
    console.error("❌ Network failure:", err);
    yield { type: "error", message: "Network error. Please retry." };
    yield { type: "done" };
    return;
  }

  if (res.status === 429) {
    console.warn("⏳ Rate limited");
    yield { type: "error", message: "Too many requests. Please wait a moment." };
    yield { type: "done" };
    return;
  }

  if (!res.ok) {
    const text = await res.text();
    console.error("❌ Transcription failed:", res.status, text);
    yield { type: "error", message: `Transcription failed (${res.status})` };
    yield { type: "done" };
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    yield { type: "error", message: "Streaming not supported" };
    yield { type: "done" };
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const json = JSON.parse(line);
        if (json.event === "final") {
          yield { type: "final", data: json };
          continue;
        }
        if ("segments" in json || "text" in json) {
          yield { type: "transcript_chunk", data: json };
          continue;
        }
      } catch {
        yield { type: "transcript", token: line };
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
        npu_utilization: [],
        memory: [],
        power: []
      };
    }
    
    const text = await res.text();
    return text ? JSON.parse(text) : {
      cpu_utilization: [],
      gpu_utilization: [],
      npu_utilization: [],
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

export const startVideoAnalyticsPipeline = startVideoAnalytics;

export const checkRecordedVideos = async (sessionId: string): Promise<any> => {
  return safeApiCall(async () => {
    const response = await fetch(`${BASE_URL}/check-recorded-videos`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': sessionId,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `Failed to check recorded videos: ${response.status}`);
    }

    return response.json();
  });
};

export const getRecordedVideoUrl = (sessionId: string, videoType: string): string => {
  if (!sessionId || !videoType) {
    throw new Error('Session ID and video type are required');
  }
  return `${BASE_URL}/recorded-video/${videoType}?session_id=${sessionId}`;
};

export async function getClassStatistics(
  sessionId: string,
  onData: (data: {
    student_count: number;
    stand_count: number;
    raise_up_count: number;
    stand_reid: { student_id: number; count: number }[];
  }) => void,
  onError?: (error: Error) => void
): Promise<() => void> {
  return safeApiCall(async () => {
    const response = await fetch(`${BASE_URL}/class-statistics`, {
      method: 'GET',
      headers: {
        'x-session-id': sessionId,
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No reader available');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    const processStream = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          
          // Process complete JSON objects
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer
          
          for (const line of lines) {
            if (line.trim()) {
              try {
                const data = JSON.parse(line);
                if (data.error) {
                  onError?.(new Error(data.error));
                } else {
                  onData(data);
                }
              } catch (parseError) {
                console.warn('Failed to parse JSON:', line, parseError);
              }
            }
          }
        }
      } catch (error) {
        onError?.(error as Error);
      } finally {
        reader.releaseLock();
      }
    };

    processStream();

    // Return cleanup function
    return () => {
      reader.cancel();
    };
  });
}

export async function* monitorVideoAnalyticsPipelines(
  sessionId: string,
  signal?: AbortSignal
): AsyncGenerator<any, void, unknown> {

  console.log("🎥 Starting video pipeline monitor:", sessionId);

  const response = await fetch(
    `${BASE_URL}/monitor-video-analytics-pipeline`,
    {
      method: "GET",
      headers: {
        "x-session-id": sessionId
      },
      signal
    }
  );

  if (!response.ok || !response.body) {
    throw new Error(`Monitor failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) return;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) continue;
      const parsed = JSON.parse(line);
    yield parsed;
        }
      }
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

export async function startMicrophone(sessionId: string): Promise<{ status: string; message: string }> {
  const res = await fetch(`${BASE_URL}/transcribe`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
      "x-session-id": sessionId, // Use provided session ID
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

  console.log("🎙️ Microphone started with session ID:", sessionId);

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
    message: "Microphone streaming started successfully."
  };
}

export async function csUploadIngest(
  file: File,
  meta?: Record<string, unknown>
): Promise<{ task_id: string; status: string; file_key?: string }> {
  return safeApiCall(async () => {
    const form = new FormData();
    form.append('file', file);
    if (meta) {
      form.append('meta', JSON.stringify(meta));
    }
    const res = await fetch(`${CONTENT_SEARCH_API_URL}/api/v1/object/upload-ingest`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const json = await res.json().catch(() => ({}));
      throw new Error(json.message || `Upload-ingest failed (${res.status})`);
    }
    const data = await res.json();
    // code 40901 = file already exists; backend returns task_id for cleanup
    if (data.code === 40901) {
      return { task_id: data.data?.task_id ?? '', status: 'ALREADY_EXISTS', file_key: data.data?.file_key };
    }
    const payload = data.data ?? data;
    if (!payload?.task_id) {
      throw new Error('upload-ingest response missing task_id');
    }
    return payload;
  });
}

export async function csIngest(
  fileKey: string,
  meta: Record<string, unknown>,
  bucketName = 'content-search'
): Promise<{ task_id: string; status: string }> {
  return safeApiCall(async () => {
    const res = await fetch(`${CONTENT_SEARCH_API_URL}/api/v1/object/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bucket_name: bucketName, file_key: fileKey, meta }),
    });
    if (!res.ok) {
      const json = await res.json().catch(() => ({}));
      throw new Error(json.message || `Ingest failed (${res.status})`);
    }
    const data = await res.json();
    return data.data ?? data;
  });
}

export async function csQueryTask(taskId: string): Promise<{
  task_id: string;
  status: string;
  progress: number;
  result?: Record<string, unknown>;
}> {
  return safeApiCall(async () => {
    const res = await fetch(`${CONTENT_SEARCH_API_URL}/api/v1/task/query/${encodeURIComponent(taskId)}`, {
      cache: 'no-store',
    });
    if (!res.ok) {
      const json = await res.json().catch(() => ({}));
      throw new Error(json.message || `Task query failed (${res.status})`);
    }
    const data = await res.json();
    return data.data ?? data;
  });
}

export async function csCleanupTask(
  taskId: string
): Promise<{ code: number; task_id: string; status: string; message: string }> {
  return safeApiCall(async () => {
    const res = await fetch(
      `${CONTENT_SEARCH_API_URL}/api/v1/object/cleanup-task/${encodeURIComponent(taskId)}`,
      { method: 'DELETE' }
    );
    const data = await res.json().catch(() => ({}));
    return {
      code: data.code ?? 20000,
      task_id: data.data?.task_id ?? taskId,
      status: data.data?.status ?? 'COMPLETED',
      message: data.message ?? '',
    };
  });
}

export async function createSession(): Promise<{ sessionId: string }> {
  return safeApiCall(async () => {
    const res = await fetch(`${BASE_URL}/create-session`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
 
    if (!res.ok) {
      const errorText = await res.text();
      console.error('❌ Failed to create session:', errorText);
      throw new Error(`Failed to create session: ${res.status}`);
    }
 
    const data = await res.json();
    const sessionId = data['session-id'];
    console.log('🟢 Session ID created:', sessionId);
 
    return { sessionId };
  });
}

export async function startMonitoring(sessionId: string): Promise<{ status: string; message: string }> {
  return safeApiCall(async () => {
    console.log('📊 Starting monitoring for session:', sessionId);
    const res = await fetch(`${BASE_URL}/start-monitoring`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'x-session-id': sessionId  // Pass session ID in header like transcription
      },
    });
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Failed to start monitoring: ${res.status} - ${errorText}`);
    }
    return await res.json();
  });
}

export async function stopMonitoring(): Promise<{ status: string; message: string }> {
  return safeApiCall(async () => {
    console.log('🛑 Stopping monitoring');
    const res = await fetch(`${BASE_URL}/stop-monitoring`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json'
      },
    });
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Failed to stop monitoring: ${res.status} - ${errorText}`);
    }
    return await res.json();
  });
}

export async function generateContentSegmentation(sessionId: string): Promise<{ session_id: string }> {
  return safeApiCall(async () => {
    const response = await fetch(`${BASE_URL}/content-segmentation`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ session_id: sessionId }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Content segmentation failed: ${response.status} - ${errorText}`);
    }

    return await response.json();
  });
}

export async function uploadVideoMetadata(sessionId: string, videoFile: File): Promise<{ status: string; message: string }> {
  return safeApiCall(async () => {
    console.log(`📹 Extracting video duration from ${videoFile.name}...`);
    // Extract duration from video file using HTML5 Video API
    const duration = await getVideoDuration(videoFile);
    
    if (!duration) {
      throw new Error('Could not extract video duration from file');
    }

    console.log(`📤 Sending video duration to backend: ${duration.toFixed(2)}s`);
    // Send duration to backend
    const response = await fetch(`${BASE_URL}/store-video-duration`, {
      method: 'POST',
      headers: {
        'X-Session-ID': sessionId,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ duration }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Video metadata upload failed: ${response.status} - ${errorText}`);
    }

    const result = await response.json();
    console.log('✅ Video duration stored at backend:', result);
    return result;
  });
}

/**
 * Extract video duration using HTML5 Video API
 * This is more reliable than ffprobe and works in the browser
 */
export function getVideoDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    try {
      const video = document.createElement('video');
      const url = URL.createObjectURL(file);
      
      // Set a timeout in case metadata never loads
      const timeout = setTimeout(() => {
        URL.revokeObjectURL(url);
        console.warn('Video duration extraction timed out');
        resolve(null);
      }, 10000); // 10 second timeout

      video.addEventListener('loadedmetadata', () => {
        clearTimeout(timeout);
        URL.revokeObjectURL(url);
        const duration = video.duration;
        console.log(`✅ Extracted video duration: ${duration.toFixed(2)}s`);
        resolve(isFinite(duration) ? duration : null);
      }, { once: true });

      video.addEventListener('error', () => {
        clearTimeout(timeout);
        URL.revokeObjectURL(url);
        console.warn('Error loading video metadata');
        resolve(null);
      }, { once: true });

      // Trigger metadata loading
      video.src = url;
      video.load();
    } catch (error) {
      console.error('Error extracting video duration:', error);
      resolve(null);
    }
  });
}

export async function markVideoUsage(sessionId: string): Promise<{ status: string; message: string }> {
  return safeApiCall(async () => {
    const response = await fetch(`${BASE_URL}/mark-video-usage`, {
      method: 'POST',
      headers: {
        'X-Session-ID': sessionId,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to mark video usage: ${response.status} - ${errorText}`);
    }

    return await response.json();
  });
}

export async function searchContent(sessionId: string, query: string, topK: number = 5): Promise<SearchResult> {
  return safeApiCall(async () => {
    const response = await fetch(`${BASE_URL}/search-content`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        query: query,
        top_k: topK
      }),
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Search failed: ${response.status} - ${errorText}`);
    }
    return await response.json();
  });
}

// Content Search API - search for objects
export async function csSearch(params: CsSearchParams): Promise<CsSearchResult[]> {
  try {
    const response = await fetch(`${CONTENT_SEARCH_API_URL}/api/v1/object/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(params),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Content search failed: ${response.status} - ${errorText}`);
    }

    const data = await response.json();
    // API returns { code, data: { results: [...] }, message, timestamp }
    return Array.isArray(data?.data?.results) ? data.data.results : [];
  } catch (error) {
    console.error('csSearch error:', error);
    return [];
  }
}