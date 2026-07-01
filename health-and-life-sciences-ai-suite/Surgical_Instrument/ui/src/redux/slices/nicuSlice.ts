import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { NicuState } from '../../types/nicu';

interface NicuSliceState {
  data: NicuState;
  expandedSection: 'video' | null;
}

const initialState: NicuSliceState = {
  data: {
    systemStatus: 'ready',
    polyp: { detected: false, count: 0, confidence: 0 },
    pipelinePerformance: { workloads: [], pipeline_fps: 0, decode: '' },
    frameUrl: null,
    fps: 0,
    uptime: 0,
  },
  expandedSection: null,
};

const nicuSlice = createSlice({
  name: 'nicu',
  initialState,
  reducers: {
    updateNicuState(state, action: PayloadAction<NicuState>) {
      state.data = action.payload;
    },
    patchNicuState(state, action: PayloadAction<Partial<NicuState>>) {
      state.data = { ...state.data, ...action.payload };
    },
    resetNicuState(state) {
      state.data = initialState.data;
      state.expandedSection = null;
    },
    setExpandedSection(state, action: PayloadAction<'video' | null>) {
      state.expandedSection =
        state.expandedSection === action.payload ? null : action.payload;
    },
  },
});

export const { updateNicuState, patchNicuState, resetNicuState, setExpandedSection } = nicuSlice.actions;
export default nicuSlice.reducer;
