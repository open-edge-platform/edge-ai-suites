import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import { WORKLOADS } from '../../constants';

interface WorkloadState {
  status: 'idle' | 'running' | 'stopped' | 'error';
  eventCount: number;
  latestData: any;
  lastEventTime: number | null;
}

interface MetricsState {
  total_events: number;
  events_per_sec: number;
  cpu_usage: number;
  gpu_usage: number;
  memory_usage: number;
  power_usage: number;
  uptime: number;
}

interface ServicesState {
  aggregator: {
    status: 'disconnected' | 'connecting' | 'connected' | 'error';
  };
  workloads: Record<string, WorkloadState>;
  metrics: MetricsState;
  platform: any;
  platformInfo: any;
}

// Helper function to create workload state with mock data
const createWorkloadState = (workloadId: string): WorkloadState => {
  const workloadConfig = WORKLOADS.find(w => w.id === workloadId);
  
  return {
    status: 'idle',
    eventCount: Math.floor(Math.random() * 200) + 50, // Random 50-250
    latestData: workloadConfig?.mockVitals || {},
    lastEventTime: Date.now(),
  };
};

const initialState: ServicesState = {
  aggregator: { 
    status: 'connected' // Change to 'connected' for Phase 1 mock
  },
  workloads: {
    rppg: createWorkloadState('rppg'),
    'ai-ecg': createWorkloadState('ai-ecg'),
    mdpnp: createWorkloadState('mdpnp'),
    '3d-pose': createWorkloadState('3d-pose'),
  },
  metrics: {
    total_events: 450,
    events_per_sec: 15,
    cpu_usage: 45,
    gpu_usage: 60,
    memory_usage: 8500, // MB
    power_usage: 28, // Watts
    uptime: 930, // seconds
  },
  platform: {
    Processor: 'Intel Core Ultra 7',
    NPU: 'Intel AI Boost',
    iGPU: 'Intel Arc Graphics',
    Memory: '32GB DDR5',
    Storage: '1TB NVMe SSD',
  },
  platformInfo: null,
};

const servicesSlice = createSlice({
  name: 'services',
  initialState,
  reducers: {
    setAggregatorStatus: (state, action: PayloadAction<ServicesState['aggregator']['status']>) => {
      state.aggregator.status = action.payload;
    },
    updateWorkloadStatus: (
      state,
      action: PayloadAction<{ workloadId: string; status: WorkloadState['status'] }>
    ) => {
      const { workloadId, status } = action.payload;
      if (state.workloads[workloadId]) {
        state.workloads[workloadId].status = status;
      }
    },
    updateWorkloadData: (
      state,
      action: PayloadAction<{ workloadId: string; data: any }>
    ) => {
      const { workloadId, data } = action.payload;
      if (state.workloads[workloadId]) {
        state.workloads[workloadId].latestData = data;
        state.workloads[workloadId].eventCount += 1;
        state.workloads[workloadId].lastEventTime = Date.now();
      }
    },
    updateMetrics: (state, action: PayloadAction<Partial<MetricsState>>) => {
      state.metrics = { ...state.metrics, ...action.payload };
    },
    setPlatformInfo: (state, action: PayloadAction<any>) => {
      state.platformInfo = action.payload;
    },
    resetWorkloads: (state) => {
      Object.keys(state.workloads).forEach((key) => {
        state.workloads[key].status = 'idle';
        state.workloads[key].eventCount = 0;
        state.workloads[key].lastEventTime = null;
      });
    },
  },
});

export const {
  setAggregatorStatus,
  updateWorkloadStatus,
  updateWorkloadData,
  updateMetrics,
  setPlatformInfo,
  resetWorkloads,
} = servicesSlice.actions;

export default servicesSlice.reducer;