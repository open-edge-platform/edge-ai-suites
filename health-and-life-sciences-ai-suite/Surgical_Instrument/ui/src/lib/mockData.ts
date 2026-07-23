// src/lib/mockData.ts
//
// Mock data shaped to EXACTLY match the current MVP backend SSE/status payload
// (/events + /status + /health).
//
// Field names, types, and nesting match the real backend so that
// when the SSE hook is wired in, the adapter is trivial.

import type { DetectionState } from '../types/detection';

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

export const mockDetectionState: DetectionState = {
  systemStatus: 'running',
  pipelinePerformance: {
    workloads: [{
      name: 'Polyp Detection',
      device: 'GPU',
      status: 'running',
      fps: 28.5,
      processing_mean_ms: 12.3,
      processing_p50_ms: 11.8,
      processing_p90_ms: 13.6,
      processing_p95_ms: 14.1,
      processing_p99_ms: 15.0,
    }],
    pipeline_fps: 28.5,
    decode: '1920x1080 H.264',
  },
  pipelineLatency: {
    mean_ms: 12.3,
    p50_ms: 11.8,
    p90_ms: 13.6,
    p95_ms: 14.1,
    p99_ms: 15.0,
  },
  modelInfo: {
    name: 'yolo11n-polyp',
    precision: 'FP16 OpenVINO IR',
    task: 'Polyp Detection',
    dataset: 'CVC-ColonDB',
    input_source: 'Recorded file',
    model_input: '640x640',
    device: 'GPU',
  },
  fps: 28.5,
  uptime: 342,
  totalFrames: 8452,
  inferP50Ms: 0,
  inferP90Ms: 0,
  inferP95Ms: 0,
  inferP99Ms: 0,
  totalP50Ms: 11.8,
  totalP90Ms: 13.6,
  totalP95Ms: 14.1,
  totalP99Ms: 15.0,
};

// ─── Live mock updater ────────────────────────────────────────────────────────
export function generateLiveMockState(prev: DetectionState): DetectionState {
  const jitter = (val: number, range: number) =>
    Math.round((val + (Math.random() - 0.5) * range) * 100) / 100;
  const mean = Math.max(1, jitter(prev.pipelineLatency.mean_ms, 1.5));
  const p50 = Math.max(1, jitter(prev.pipelineLatency.p50_ms, 1.2));
  const p90 = Math.max(p50, jitter(prev.pipelineLatency.p90_ms, 1.5));
  const p95 = Math.max(p90, jitter(prev.pipelineLatency.p95_ms, 1.2));
  const p99 = Math.max(p95, jitter(prev.pipelineLatency.p99_ms, 1.0));

  return {
    ...prev,
    fps: Math.round(jitter(28.5, 3) * 10) / 10,
    uptime: prev.uptime + 1,
    totalFrames: prev.totalFrames + Math.floor(Math.random() * 3 + 1),
    pipelineLatency: {
      mean_ms: mean,
      p50_ms: p50,
      p90_ms: p90,
      p95_ms: p95,
      p99_ms: p99,
    },
    pipelinePerformance: {
      ...prev.pipelinePerformance,
      pipeline_fps: Math.round(jitter(28.5, 3) * 10) / 10,
      workloads: prev.pipelinePerformance.workloads.map((w) => ({
        ...w,
        fps: Math.round(jitter(w.fps ?? 28.5, 2) * 10) / 10,
        processing_mean_ms: mean,
        processing_p50_ms: p50,
        processing_p90_ms: p90,
        processing_p95_ms: p95,
        processing_p99_ms: p99,
      })),
    },
    totalP50Ms: p50,
    totalP90Ms: p90,
    totalP95Ms: p95,
    totalP99Ms: p99,
  };
}