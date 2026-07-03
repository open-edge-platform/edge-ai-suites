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
      cumulative_detections: 0, frames_with_detection: 0, detection_rate: 0,
    },
    pipelinePerformance: { workloads: [], pipeline_fps: 0, decode: '' },
    modelInfo: null,
    frameUrl: null,
    fps: 0,
    uptime: 0,
    totalFrames: 0,
    inferP99Ms: 0,
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
    setExpandedSection(state, action: PayloadAction<'video' | null>) {
      state.expandedSection =
        state.expandedSection === action.payload ? null : action.payload;
    },
  },
});

export const { updateDetectionState, patchDetectionState, resetDetectionState, setExpandedSection } = detectionSlice.actions;
export default detectionSlice.reducer;
