import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { NicuState } from '../../types/nicu';

interface NicuSliceState {
  data: NicuState;
  expandedSection: 'video' | 'rppg' | null;
}

const initialState: NicuSliceState = {
  data: {
    systemStatus: 'ready',
    patient: { detected: false, confidence: null as unknown as number },
    caretaker: {
      detected: false,
      count: null as unknown as number,
      confidence: null as unknown as number,
    },
    latch: { state: 'unknown', confidence: null as unknown as number },
    workflow: {
      currentStep: null,
      completedSteps: [],
      timestamps: {},
    },
    action: { activities: [], top_activity: 'Warming Up', top_confidence: 0, status: 'warming_up' as const },
    rppg: {
      heartRate: null,
      respirationRate: null,
      heartRateMin: null,
      heartRateMax: null,
      confidence: 0,
      sessionDuration: 0,
      waveform: [],
      respWaveform: [],
    },
    models: [],
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
    setExpandedSection(state, action: PayloadAction<'video' | 'rppg' | null>) {
      // toggle — same pattern as setExpandedWorkload in appSlice
      state.expandedSection =
        state.expandedSection === action.payload ? null : action.payload;
    },
  },
});

export const { updateNicuState, patchNicuState, resetNicuState, setExpandedSection } = nicuSlice.actions;
export default nicuSlice.reducer;