import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

export interface PipelineMetrics {
  fps: number;
  latencyP50Ms: number;
  latencyP95Ms: number;
  latencyP99Ms: number;
  lateFramePct: number;
  framesProcessed: number;
  detectionCount: number;
  lastConfidence: number;
}

export interface SystemMetrics {
  cpuPct: number;
  gpuPct: number;
  npuPct: number;
  memUsedGib: number;
  memTotalGib: number;
}

export interface MetricsState {
  pipeline: PipelineMetrics;
  system: SystemMetrics;
  updatedAt: number;
}

const initialState: MetricsState = {
  pipeline: {
    fps: 0,
    latencyP50Ms: 0,
    latencyP95Ms: 0,
    latencyP99Ms: 0,
    lateFramePct: 0,
    framesProcessed: 0,
    detectionCount: 0,
    lastConfidence: 0,
  },
  system: {
    cpuPct: 0,
    gpuPct: 0,
    npuPct: 0,
    memUsedGib: 0,
    memTotalGib: 0,
  },
  updatedAt: 0,
};

const metricsSlice = createSlice({
  name: 'metrics',
  initialState,
  reducers: {
    setPipelineMetrics(state, action: PayloadAction<Partial<PipelineMetrics>>) {
      Object.assign(state.pipeline, action.payload);
      state.updatedAt = Date.now() / 1000;
    },
    setSystemMetrics(state, action: PayloadAction<Partial<SystemMetrics>>) {
      Object.assign(state.system, action.payload);
      state.updatedAt = Date.now() / 1000;
    },
  },
});

export const { setPipelineMetrics, setSystemMetrics } = metricsSlice.actions;
export default metricsSlice.reducer;
