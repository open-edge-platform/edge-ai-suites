// src/lib/mockData.ts
//
// Mock data shaped to EXACTLY match the current MVP backend SSE/status payload
// (/events + /status + /health + /frame/latest).
//
// Field names, types, and nesting match the real backend so that
// when the SSE hook is wired in, the adapter is trivial.

import type { NicuState } from '../types/nicu';

// ─── Waveform generator (for mock only) ──────────────────────────────────────
function generateWaveform(length: number): number[] {
  const waveform: number[] = [];
  for (let i = 0; i < length; i++) {
    waveform.push(
      Math.sin((i / length) * Math.PI * 2 * 8) * 0.6 +
      (Math.random() - 0.5) * 0.15
    );
  }
  return waveform;
}

// ─── Shape mirrors build_stream_snapshot() exactly ───────────────────────────
//
// SSE fields used:
//   snap.status.doors_latched        → latch.state
//   snap.status.patient_present      → patient.detected
//   snap.status.people_present       → caretaker.detected
//   snap.rppg_active                 → rppg session active flag
//   snap.rppg_elapsed                → rppg.sessionDuration
//   snap.rppg_metrics.heart_rate_avg → rppg.heartRate
//   snap.rppg_metrics.heart_rate_min → rppg.heartRateMin
//   snap.rppg_metrics.heart_rate_max → rppg.heartRateMax
//   snap.rppg_metrics.confidence_score → rppg.confidence
//   snap.waveform.samples            → rppg.waveform (completed session)
//   snap.waveform_append.append      → rppg.waveform append (active session)
//   snap.model_stats                 → models[] (per-model fps/latency)
//   snap.video_frame_idx             → fps proxy (frame count)
//   snap.video_loop_count            → uptime proxy
//
// NOT available from backend (shown in mock only as UI placeholder):
//   patient.confidence               → no backend equivalent; show '--' on integration
//   caretaker.confidence             → no backend equivalent; show '--' on integration
//   caretaker.count                  → no backend equivalent; backend only has bool
//   latch.confidence                 → no backend equivalent; show '--' on integration
//   systemStatus                     → derive from /health poll separately
//   fps (top-level)                  → derive from model_stats averages on integration

export const mockNicuState: NicuState = {
  // Derived from /health on integration
  systemStatus: 'running',

  // From snap.status.patient_present (bool)
  // confidence: NO backend field — UI will show signal dots as '--' when real
  patient: {
    detected: true,
    confidence: null, // explicitly null = not provided by backend
  },

  // From snap.status.people_present (bool)
  // count: NO backend field — backend only gives bool
  // confidence: NO backend field
  caretaker: {
    detected: true,
    count: null,       // not provided by backend
    confidence: null,  // not provided by backend
  },

  // From snap.status.doors_latched (bool → 'closed'|'open')
  // confidence: NO backend field
  latch: {
    state: 'closed',
    confidence: null, // not provided by backend
  },

  // From snap.rppg_metrics + snap.rppg_active + snap.rppg_elapsed
  // waveform from snap.waveform.samples (completed) or snap.waveform_append.append (active)
  rppg: {
    // snap.rppg_metrics.heart_rate_avg
    heartRate: 142,
    // snap.rppg_metrics.heart_rate_min
    heartRateMin: 136,
    // snap.rppg_metrics.heart_rate_max
    heartRateMax: 148,
    // snap.rppg_metrics.confidence_score
    confidence: 0.82,
    // snap.rppg_elapsed (seconds, 0..30)
    sessionDuration: 18,
    // snap.rppg_active
    sessionActive: true,
    // snap.waveform.samples or accumulated snap.waveform_append.append[]
    waveform: generateWaveform(200),
  },

  // From snap.model_stats — backend returns dict keyed by model name
  // Each entry has: fps, latency_ms, status ('running'|'waiting'|'error'), frames_processed
  models: [
    { name: 'person',  fps: 28.4, latency: 12.3, status: 'running', framesProcessed: 8452 },
    { name: 'patient', fps: 27.9, latency: 13.1, status: 'running', framesProcessed: 8450 },
    { name: 'latch',   fps: 29.1, latency: 11.8, status: 'running', framesProcessed: 8455 },
  ],

  // Polled from /frame/latest?t=<timestamp> as JPEG binary
  frameUrl: null,

  // Derived from model_stats average fps on integration
  fps: 28.5,

  // snap.video_loop_count on integration
  uptime: 342,
};

// ─── Live mock updater ────────────────────────────────────────────────────────
export function generateLiveMockState(prev: NicuState): NicuState {
  const jitter = (val: number, range: number) =>
    Math.round((val + (Math.random() - 0.5) * range) * 100) / 100;

  // Simulate waveform scroll (matches waveform_append.append behavior)
  const newWaveform = [...prev.rppg.waveform.slice(1)];
  newWaveform.push(
    Math.sin((Date.now() / 1000) * Math.PI * 2 * 1.2) * 0.6 +
    (Math.random() - 0.5) * 0.15
  );

  // Simulate sessionDuration counting to 30 then resetting (matches rppg_elapsed 0..30)
  const nextDuration = prev.rppg.sessionDuration >= 30
    ? 0
    : prev.rppg.sessionDuration + 1;
  const sessionActive = nextDuration > 0 && nextDuration < 30;

  return {
    ...prev,

    // Derived from model_stats on real integration
    fps: Math.round(jitter(28.5, 3) * 10) / 10,

    // snap.video_loop_count proxy
    uptime: prev.uptime + 1,

    // snap.status.patient_present
    // confidence: null — backend never sends this
    patient: {
      detected: Math.random() > 0.03,
      confidence: null,
    },

    // snap.status.people_present
    // count/confidence: null — backend never sends these
    caretaker: {
      detected: Math.random() > 0.08,
      count: null,
      confidence: null,
    },

    // snap.status.doors_latched → 'closed'|'open'
    // confidence: null — backend never sends this
    latch: {
      state: prev.uptime % 40 < 30 ? 'closed' : 'open',
      confidence: null,
    },

    // snap.rppg_metrics + snap.rppg_active + snap.rppg_elapsed + waveform
    rppg: {
      heartRate: Math.round(jitter(142, 6)),
      heartRateMin: Math.round(jitter(136, 2)),
      heartRateMax: Math.round(jitter(148, 2)),
      confidence: Math.min(1, Math.max(0, jitter(0.82, 0.1))),
      sessionDuration: nextDuration,
      sessionActive,
      waveform: newWaveform,
    },

    // snap.model_stats
    models: prev.models.map((m) => ({
      ...m,
      fps: Math.round(jitter(m.fps, 2) * 10) / 10,
      latency: Math.max(1, Math.round(jitter(m.latency, 1.5) * 10) / 10),
      framesProcessed: m.framesProcessed + Math.floor(Math.random() * 3),
    })),
  };
}