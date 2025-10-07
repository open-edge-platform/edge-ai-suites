import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';

interface ResourceMetrics {
  cpu_utilization: any[];
  gpu_utilization: any[];
  memory: any[];
  power: any[];
}

interface ResourceState {
  metrics: ResourceMetrics;
  lastUpdated: number | null;
}

const initialState: ResourceState = {
  metrics: {
    cpu_utilization: [],
    gpu_utilization: [],
    memory: [],
    power: []
  },
  lastUpdated: null
};

const resourceSlice = createSlice({
  name: 'resource',
  initialState,
  reducers: {
    setMetrics: (state, action: PayloadAction<ResourceMetrics>) => {
      state.metrics = action.payload;
      state.lastUpdated = Date.now();
    },
    clearMetrics: (state) => {
      state.metrics = initialState.metrics;
      state.lastUpdated = null;
    }
  }
});

export const { setMetrics, clearMetrics } = resourceSlice.actions;
export default resourceSlice.reducer;