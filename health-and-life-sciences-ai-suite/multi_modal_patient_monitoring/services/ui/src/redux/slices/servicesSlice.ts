import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface WorkloadState {
  status: 'idle' | 'running' | 'error';
  eventCount: number;
  lastEventTime: number | null;
  latestData: Record<string, any>;
  waveform?: number[];
  waveformType?: string;
  waveformFrequency?: number;
}

interface ServicesState {
  aggregator: {
    status: 'stopped' | 'connecting' | 'connected' | 'error';
  };
  workloads: {
    'rppg': WorkloadState;
    'ai-ecg': WorkloadState;
    'mdpnp': WorkloadState;
    '3d-pose': WorkloadState;
  };
}

const initialState: ServicesState = {
  aggregator: { status: 'stopped' },
  workloads: {
    'rppg': { status: 'idle', eventCount: 0, lastEventTime: null, latestData: {} },
    'ai-ecg': { status: 'idle', eventCount: 0, lastEventTime: null, latestData: {} },
    'mdpnp': { status: 'idle', eventCount: 0, lastEventTime: null, latestData: {} },
    '3d-pose': { 
      status: 'idle', 
      eventCount: 0, 
      lastEventTime: null, 
      latestData: {}
    },
  },
};

const servicesSlice = createSlice({
  name: 'services',
  initialState,
  reducers: {
    setAggregatorStatus: (state, action: PayloadAction<ServicesState['aggregator']['status']>) => {
      state.aggregator.status = action.payload;
    },

    updateWorkloadData: (state, action: PayloadAction<{
      workloadId: keyof ServicesState['workloads'];
      payload: any;
      timestamp: number;
    }>) => {
      const { workloadId, payload, timestamp } = action.payload;
      const workload = state.workloads[workloadId];

      if (!workload) {
        console.warn(`[Redux] ⚠️ Unknown workload: ${workloadId}`);
        return;
      }

      // Update status
      workload.status = 'running';
      workload.eventCount += 1;
      workload.lastEventTime = timestamp;

      console.log(`[Redux] 📊 Updating ${workloadId}:`, {
        eventCount: workload.eventCount,
        payloadKeys: Object.keys(payload),
        hasWaveform: !!payload.waveform
      });

      // Parse workload-specific data
      if (workloadId === 'rppg') {
        // rPPG sends: HR, RR, SpO2, waveform
        if (payload.HR !== undefined) workload.latestData.HR = payload.HR;
        if (payload.RR !== undefined) workload.latestData.RR = payload.RR;
        if (payload.SpO2 !== undefined) workload.latestData.SpO2 = payload.SpO2;
        
        if (payload.waveform && Array.isArray(payload.waveform)) {
          workload.waveform = payload.waveform;
          console.log(`[Redux] ✓ rPPG waveform: ${payload.waveform.length} samples`);
        }

        console.log(`[Redux] ✓ rPPG vitals: HR=${workload.latestData.HR}, RR=${workload.latestData.RR}, SpO2=${workload.latestData.SpO2}`);

      } else if (workloadId === 'ai-ecg') {
        // AI-ECG sends: prediction, filename, waveform, waveformFrequency
        if (payload.prediction !== undefined) {
          workload.latestData.prediction = payload.prediction;
          console.log(`[Redux] ✓ AI-ECG prediction: ${payload.prediction}`);
        }

        if (payload.filename !== undefined) {
          workload.latestData.filename = payload.filename;
          console.log(`[Redux] ✓ AI-ECG filename: ${payload.filename}`);
        }

        if (payload.waveform && Array.isArray(payload.waveform)) {
          workload.waveform = payload.waveform;
          console.log(`[Redux] ✓ AI-ECG waveform: ${payload.waveform.length} samples`);
        }

        if (payload.waveformFrequency !== undefined) {
          workload.waveformFrequency = payload.waveformFrequency;
          console.log(`[Redux] ✓ AI-ECG frequency: ${payload.waveformFrequency} Hz`);
        }

      } else if (workloadId === 'mdpnp') {
        // MDPNP sends: HR, CO2_ET, BP_DIA, waveform with type
        if (payload.HR !== undefined) {
          workload.latestData.HR = payload.HR;
          console.log(`[Redux] ✓ MDPNP HR: ${payload.HR}`);
        }
        if (payload.CO2_ET !== undefined) {
          workload.latestData.CO2_ET = payload.CO2_ET;
          console.log(`[Redux] ✓ MDPNP CO2_ET: ${payload.CO2_ET}`);
        }
        if (payload.BP_DIA !== undefined) {
          workload.latestData.BP_DIA = payload.BP_DIA;
          console.log(`[Redux] ✓ MDPNP BP_DIA: ${payload.BP_DIA}`);
        }

        if (payload.waveform && Array.isArray(payload.waveform)) {
          workload.waveform = payload.waveform;
          workload.waveformType = payload.waveformType || 'unknown';
          console.log(`[Redux] ✓ MDPNP ${workload.waveformType} waveform: ${payload.waveform.length} samples`);
        }

      } else if (workloadId === '3d-pose') {
        // 3D Pose sends: joints count, confidence, activity
        if (payload.joints !== undefined) {
          workload.latestData.joints = payload.joints;
          console.log(`[Redux] ✓ 3D Pose joints: ${payload.joints}`);
        }
        if (payload.confidence !== undefined) {
          workload.latestData.confidence = payload.confidence;
          console.log(`[Redux] ✓ 3D Pose confidence: ${payload.confidence}`);
        }
        if (payload.activity !== undefined) {
          workload.latestData.activity = payload.activity;
          console.log(`[Redux] ✓ 3D Pose activity: ${payload.activity}`);
        }
      }
    },

    resetWorkloadData: (state, action: PayloadAction<keyof ServicesState['workloads']>) => {
      const workloadId = action.payload;
      state.workloads[workloadId] = {
        status: 'idle',
        eventCount: 0,
        lastEventTime: null,
        latestData: {},
        waveform: undefined,
        waveformType: undefined,
        waveformFrequency: undefined,
      };
      console.log(`[Redux] 🔄 Reset ${workloadId} data`);
    },

    startAllWorkloads: (state) => {
      Object.values(state.workloads).forEach((workload) => {
        workload.status = 'running';
      });
      console.log('[Redux] ▶️ All workloads started');
    },

    stopAllWorkloads: (state) => {
      Object.values(state.workloads).forEach((workload) => {
        workload.status = 'idle';
      });
      console.log('[Redux] ⏹️ All workloads stopped');
    },
  },
});

export const {
  setAggregatorStatus,
  updateWorkloadData,
  resetWorkloadData,
  startAllWorkloads,
  stopAllWorkloads,
} = servicesSlice.actions;

export default servicesSlice.reducer;