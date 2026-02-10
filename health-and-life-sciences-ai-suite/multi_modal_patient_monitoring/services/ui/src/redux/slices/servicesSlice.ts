import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { WorkloadId } from '../../constants';

interface WorkloadState {
  status: 'idle' | 'running' | 'error';
  eventCount: number;
  lastEventTime: number | null;
  latestData: Record<string, any>;
  waveform?: number[];
  frameData?: string; 
}

interface ServicesState {
  aggregator: {
    status: 'stopped' | 'connecting' | 'connected' | 'error';
  };
  workloads: Record<WorkloadId, WorkloadState>;
}

const initialState: ServicesState = {
  aggregator: { status: 'stopped' },
  workloads: {
    'rppg': { status: 'idle', eventCount: 0, lastEventTime: null, latestData: {} },
    'ai-ecg': { status: 'idle', eventCount: 0, lastEventTime: null, latestData: {} },
    'mdpnp': { status: 'idle', eventCount: 0, lastEventTime: null, latestData: {} },
    '3d-pose': { status: 'idle', eventCount: 0, lastEventTime: null, latestData: {}, frameData: undefined },
  },
};

const servicesSlice = createSlice({
  name: 'services',
  initialState,
  reducers: {
    setAggregatorStatus: (state, action: PayloadAction<ServicesState['aggregator']['status']>) => {
      state.aggregator.status = action.payload;
    },

    updateWorkloadData: (
      state,
      action: PayloadAction<{
        workloadId: WorkloadId;
        payload: any;
        timestamp: number;
      }>
    ) => {
      const { workloadId, payload, timestamp } = action.payload;
      const workload = state.workloads[workloadId];

      if (!workload) {
        console.warn(`[Redux] ⚠️ Unknown workload: ${workloadId}`);
        return;
      }

      workload.status = 'running';
      workload.eventCount += 1;
      workload.lastEventTime = timestamp;

      console.log(`[Redux] Processing ${workloadId}:`, {
        keys: Object.keys(payload),
        hasWaveform: !!payload.waveform
      });

      // ✅ Handle waveform data
      if (payload.waveform && Array.isArray(payload.waveform)) {
        workload.waveform = payload.waveform;
        console.log(`[Redux] Stored waveform for ${workloadId}: ${payload.waveform.length} samples`);
      }

      // ✅ Extract vitals based on workload type
      if (workloadId === 'rppg') {
        // rPPG sends: HR, RR, SpO2
        if (payload.HR !== undefined) workload.latestData.HR = payload.HR;
        if (payload.RR !== undefined) workload.latestData.RR = payload.RR;
        if (payload.SpO2 !== undefined) workload.latestData.SpO2 = payload.SpO2;
        
        console.log(`[Redux] ✓ rPPG data: HR=${payload.HR}, RR=${payload.RR}, SpO2=${payload.SpO2}`);
        
      } else if (workloadId === 'ai-ecg') {
        // AI-ECG sends: inference object
        console.log('[Redux] 🔬 AI-ECG raw payload:', JSON.stringify(payload, null, 2));
        
        if (payload.prediction !== undefined) {
          workload.latestData.prediction = payload.prediction;
        }

        // Store filename
        if (payload.filename !== undefined) {
          workload.latestData.filename = payload.filename;
        }
        console.log('[Redux] ✅ AI-ECG stored:', workload.latestData);

      } else if (workloadId === 'mdpnp') {
        // MDPNP sends: metric + value (numeric) or waveform
        console.log('[Redux] 🏥 MDPNP raw payload:', JSON.stringify(payload, null, 2));
        
        // Store vitals
        if (payload.HR !== undefined) workload.latestData.HR = payload.HR;
        if (payload.CO2_ET !== undefined) workload.latestData.CO2_ET = payload.CO2_ET;
        if (payload.BP_DIA !== undefined) workload.latestData.BP_DIA = payload.BP_DIA;
        
        // Store waveform (prioritize ECG_LEAD_II for display)
        if (payload.waveform && Array.isArray(payload.waveform)) {
          workload.waveform = payload.waveform;
          console.log(`[Redux] ✓ MDPNP waveform (${payload.waveformType}):`, payload.waveform.length, 'samples');
        }
        
        console.log(`[Redux] ✓ MDPNP stored:`, {
          vitals: { HR: workload.latestData.HR, CO2_ET: workload.latestData.CO2_ET, BP_DIA: workload.latestData.BP_DIA },
          hasWaveform: !!workload.waveform
        });
      } else if (workloadId === '3d-pose') {
        // 3D Pose sends: joints array
        if (payload.joints) {
          workload.latestData.joints = Array.isArray(payload.joints) ? payload.joints.length : payload.joints;
          workload.latestData.confidence = payload.confidence || 0;
          console.log(`[Redux] ✓ 3D Pose joints: ${workload.latestData.joints}`);
        }

        // ✅ Store frame data
        if (payload.frameData) {
          workload.frameData = payload.frameData;
          console.log(`[Redux] ✓ 3D Pose frame updated`);
        }
      }

      console.log(`[Redux] ✅ Updated ${workloadId}:`, {
        eventCount: workload.eventCount,
        status: workload.status,
        latestData: workload.latestData,
        hasWaveform: !!workload.waveform
      });
    },
    startAllWorkloads: (state) => {
      Object.keys(state.workloads).forEach((key) => {
        state.workloads[key].status = 'running';
      });
    },
    stopAllWorkloads: (state) => {
      Object.keys(state.workloads).forEach((key) => {
        state.workloads[key].status = 'stopped';
      });
    },

    resetWorkloadData: (state, action: PayloadAction<WorkloadId>) => {
      const workloadId = action.payload;
      state.workloads[workloadId] = {
        status: 'idle',
        eventCount: 0,
        lastEventTime: null,
        latestData: {},
      };
    },
  },
});

export const { setAggregatorStatus, updateWorkloadData, resetWorkloadData, startAllWorkloads,
  stopAllWorkloads, } = servicesSlice.actions;
export default servicesSlice.reducer;