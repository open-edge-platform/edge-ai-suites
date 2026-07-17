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
  // Lower threshold suits normalized browser-mic audio.
  silenceThreshold: 300,
} as const;

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10 MB
export const ALLOWED_EXTENSIONS = [".txt", ".md", ".docx", ".pdf"];
export const POLL_INTERVAL_MS = 400;
