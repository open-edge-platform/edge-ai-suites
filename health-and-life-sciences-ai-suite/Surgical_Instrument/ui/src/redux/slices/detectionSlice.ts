import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { DetectionState } from '../../types/detection';

interface DetectionSliceState {
  data: DetectionState;
  expandedSection: 'video' | null;
}

const initialState: DetectionSliceState = {
  data: {
    systemStatus: 'ready',
    polyp: {
      detected: false, count: 0, confidence: 0,
      distinct_polyps: 0,
      frames_processed: 0, frames_with_detection: 0, detection_rate: 0,
      peak_confidence: 0, session_seconds: 0,
    },
    pipelinePerformance: { workloads: [], pipeline_fps: 0, decode: '' },
    modelInfo: null,
    frameUrl: null,
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
  expandedSection: null,
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
      state.expandedSection = null;
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
    setExpandedSection(state, action: PayloadAction<'video' | null>) {
      state.expandedSection =
        state.expandedSection === action.payload ? null : action.payload;
    },
  },
});

export const { updateDetectionState, patchDetectionState, resetDetectionState, setActiveDevice, setExpandedSection } = detectionSlice.actions;
export default detectionSlice.reducer;
