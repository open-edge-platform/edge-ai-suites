import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { DetectionState } from '../../types/detection';

interface DetectionSliceState {
  data: DetectionState;
}

const initialState: DetectionSliceState = {
  data: {
    systemStatus: 'ready',
    pipelinePerformance: { workloads: [], pipeline_fps: 0, decode: '' },
    pipelineLatency: { mean_ms: 0, p50_ms: 0, p90_ms: 0, p95_ms: 0, p99_ms: 0 },
    modelInfo: null,
    fps: 0,
    uptime: 0,
    totalFrames: 0,
    inferP50Ms: 0,
    inferP90Ms: 0,
    inferP95Ms: 0,
    inferP99Ms: 0,
    totalP50Ms: 0,
    totalP90Ms: 0,
    totalP95Ms: 0,
    totalP99Ms: 0,
  },
};

const detectionSlice = createSlice({
  name: 'detection',
  initialState,
  reducers: {
    updateDetectionState(state, action: PayloadAction<DetectionState>) {
      state.data = action.payload;
    },
    patchDetectionState(state, action: PayloadAction<Partial<DetectionState>>) {
      state.data = { ...state.data, ...action.payload };
    },
    resetDetectionState(state) {
      state.data = initialState.data;
    },
    setActiveDevice(state, action: PayloadAction<string>) {
      // Optimistic device swap for the frozen post-stop state: SSE is closed,
      // so patch the pill + Model Info block directly until the next Start
      // pulls a fresh snapshot from the backend.
      const dev = action.payload;
      if (state.data.modelInfo) {
        state.data.modelInfo = { ...state.data.modelInfo, device: dev };
      }
      const wls = state.data.pipelinePerformance?.workloads ?? [];
      state.data.pipelinePerformance = {
        ...state.data.pipelinePerformance,
        workloads: wls.length > 0
          ? wls.map((w, i) => (i === 0 ? { ...w, device: dev } : w))
          : [{ name: 'Polyp Detection', device: dev, fps: 0, status: 'stopped' } as any],
      };
    },
  },
});

export const { updateDetectionState, patchDetectionState, resetDetectionState, setActiveDevice } = detectionSlice.actions;
export default detectionSlice.reducer;
