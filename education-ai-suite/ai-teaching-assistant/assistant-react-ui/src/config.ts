// Central configuration for the React UI.
// All backend calls go through the same-origin proxy exposed by
// kiosk_ui_server.py (production) or the Vite dev proxy (development).

export const API = {
  kiosk: "/api/kiosk",
  rag: "/api/rag",
  tts: "/api/tts",
  analyzer: "/api/analyzer",
} as const;

// Voice capture / session tuning.
export const AUDIO = {
  sampleRate: 16000,
  // How often (seconds of audio) we flush a chunk to kiosk-core.
  chunkSeconds: 1.0,
  // Session-level pacing forwarded to kiosk-core.
  sessionChunkSeconds: 5.0,
  silenceTimeoutSeconds: 2.0,
  maxSessionSeconds: 60.0,
  // Browser-mic audio can be much quieter than native capture; keep this low
  // so speech is consistently detected and forwarded for transcription.
  silenceThreshold: 80,
  // Frontend auto-stop: after speech has started, stop recording when this
  // much near-silence is observed continuously.
  autoStopPauseMs: 3000,
  // Normalized mic level threshold [0..1] treated as speech for auto-stop.
  autoStopSpeechLevel: 0.06,
} as const;

export const WAKEWORD = {
  enabledByDefault: false,
  model: "hey jarvis",
  threshold: 0.5,
  vadThreshold: 0.4,
  patienceFrames: 2,
  timeoutSeconds: 0,
  inferenceFramework: "onnx",
} as const;

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10 MB
export const ALLOWED_EXTENSIONS = [".txt", ".md", ".docx", ".pdf"];
export const POLL_INTERVAL_MS = 400;

// Auto-reset the conversation after this many milliseconds of inactivity
// (measured from when the assistant finishes speaking). Paused while
// recording, processing, or playing back a response.
export const INACTIVITY_RESET_MS = 15_000;
