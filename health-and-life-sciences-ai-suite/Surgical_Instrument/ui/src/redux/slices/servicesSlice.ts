import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface WorkloadState {
  status: 'idle' | 'running' | 'stopped' | 'error';
  eventCount: number;
  latestData: Record<string, any>;
  lastEventTime: number | null;
}

interface ServicesState {
  aggregator: { status: 'stopped' | 'connecting' | 'connected' | 'error' };
  workloads: Record<string, WorkloadState>;
}

const initialState: ServicesState = {
  aggregator: { status: 'stopped' },
  workloads: {
    polyp: { status: 'idle', eventCount: 0, lastEventTime: null, latestData: {} },
  },
};

const servicesSlice = createSlice({
  name: 'services',
  initialState,
  reducers: {
    setAggregatorStatus(state, action: PayloadAction<ServicesState['aggregator']['status']>) {
      state.aggregator.status = action.payload;
    },
    updateWorkloadData(
      state,
      action: PayloadAction<{ workloadId: string; data: any; timestamp: number }>,
    ) {
      const { workloadId, data, timestamp } = action.payload;
      if (!state.workloads[workloadId]) {
        state.workloads[workloadId] = { status: 'idle', eventCount: 0, lastEventTime: null, latestData: {} };
      }
      state.workloads[workloadId].status = 'running';
      state.workloads[workloadId].eventCount += 1;
      state.workloads[workloadId].lastEventTime = timestamp;
      state.workloads[workloadId].latestData = { ...state.workloads[workloadId].latestData, ...data };
    },
    startAllWorkloads(state) {
      Object.values(state.workloads).forEach((w) => { w.status = 'running'; });
    },
    stopAllWorkloads(state) {
      Object.values(state.workloads).forEach((w) => { w.status = 'stopped'; });
    },
  },
});

export const {
  setAggregatorStatus,
  updateWorkloadData,
  startAllWorkloads,
  stopAllWorkloads,
} = servicesSlice.actions;
export default servicesSlice.reducer;
