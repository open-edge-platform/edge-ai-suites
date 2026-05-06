import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface MetricsState {
  platform: {
    Processor?: string;    // Was: processor
    NPU?: string;          // Was: npu
    iGPU?: string;         // Was: igpu
    Memory?: string;       // Was: memory
    Storage?: string;      // Was: storage
    OS?: string;           // Was: os
  } | null;
  
  resources: {
    cpu_utilization: Array<[string, number]>;
    gpu_utilization: Array<[string, number]>;
    memory: Array<[string, number, number, number, number]>;
    power: Array<[string, ...number[]]>;
    npu_utilization: Array<[string, number]>;
  };
  lastUpdated: number | null;
}

const initialState: MetricsState = {
  platform: null,
  resources: {
    cpu_utilization: [],
    gpu_utilization: [],
    memory: [],
    power: [],
    npu_utilization: [],
  },
  lastUpdated: null,
};

const metricsSlice = createSlice({
  name: 'metrics',
  initialState,
  reducers: {
    setPlatformInfo: (state, action: PayloadAction<any>) => {
      state.platform = action.payload;
    },
    setMetrics: (state, action: PayloadAction<any>) => {
      state.resources = {
        ...state.resources,
        ...action.payload,
      };
      state.lastUpdated = Date.now();
    },
    clearMetrics: (state) => {
      state.resources = initialState.resources;
      state.lastUpdated = null;
    },
  },
});

export const { setPlatformInfo, setMetrics, clearMetrics } = metricsSlice.actions;
export default metricsSlice.reducer;