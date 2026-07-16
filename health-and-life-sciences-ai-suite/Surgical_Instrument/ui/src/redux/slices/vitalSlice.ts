// src/redux/slices/vitalsSlice.ts
import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

interface VitalsState {
  heartRate: number | null;
  respirationRate: number | null;
  lastUpdate: string | null;
}

const initialState: VitalsState = {
  heartRate: null,
  respirationRate: null,
  lastUpdate: null,
};

const vitalsSlice = createSlice({
  name: 'vitals',
  initialState,
  reducers: {
    updateVital: (state, action: PayloadAction<{ metric: 'HR' | 'RR'; value: number }>) => {
      if (action.payload.metric === 'HR') {
        state.heartRate = action.payload.value;
      } else {
        state.respirationRate = action.payload.value;
      }
      state.lastUpdate = new Date().toISOString();
    },
  },
});

export const { updateVital } = vitalsSlice.actions;
export default vitalsSlice.reducer;