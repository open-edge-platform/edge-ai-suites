// src/redux/slices/metricsSlice.ts
import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface MetricsState {
  cpu_utilization: Array<[string, number]>;
  gpu_utilization: Array<[string, number]>;
  memory: Array<[string, number, number, number, number]>; // [timestamp, total, used, free, percent]
  power: Array<[string, ...number[]]>;
  npu_utilization: Array<[string, number]>;
}

const initialState: MetricsState = {
  cpu_utilization: [],
  gpu_utilization: [],
  memory: [],
  power: [],
  npu_utilization: [],
};

const metricsSlice = createSlice({
  name: 'metrics',
  initialState,
  reducers: {
    setMetrics: (state, action: PayloadAction<Partial<MetricsState>>) => {
      if (action.payload.cpu_utilization) {
        state.cpu_utilization = action.payload.cpu_utilization;
      }
      if (action.payload.gpu_utilization) {
        state.gpu_utilization = action.payload.gpu_utilization;
      }
      if (action.payload.memory) {
        state.memory = action.payload.memory;
      }
      if (action.payload.power) {
        state.power = action.payload.power;
      }
      if (action.payload.npu_utilization) {
        state.npu_utilization = action.payload.npu_utilization;
      }
    },
    clearMetrics: (state) => {
      state.cpu_utilization = [];
      state.gpu_utilization = [];
      state.memory = [];
      state.power = [];
      state.npu_utilization = [];
    },
  },
});

export const { setMetrics, clearMetrics } = metricsSlice.actions;
export default metricsSlice.reducer;