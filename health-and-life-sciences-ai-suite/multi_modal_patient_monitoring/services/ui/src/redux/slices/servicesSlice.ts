<<<<<<< HEAD
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
=======
import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface WorkloadState {
  status: 'idle' | 'running' | 'stopped' | 'error';
  eventCount: number;
  latestData: Record<string, any>;
  lastEventTime: number | null;
  waveform?: number[];
  frameData?: string;
  joints?: Array<{
    x: number;
    y: number;
    z: number;
    visibility?: number;
  }>;
  people?: Array<{
    person_id: number;
    joints_3d: Array<{
      x: number;
      y: number;
      z: number;
      visibility?: number;
    }>;
    confidence?: number[];
  }>;
>>>>>>> dev
}

interface ServicesState {
  aggregator: {
    status: 'stopped' | 'connecting' | 'connected' | 'error';
  };
<<<<<<< HEAD
  workloads: Record<WorkloadId, WorkloadState>;
=======
  workloads: {
    'rppg': WorkloadState;
    'ai-ecg': WorkloadState;
    'mdpnp': WorkloadState;
    '3d-pose': WorkloadState;
  };
>>>>>>> dev
}

const initialState: ServicesState = {
  aggregator: { status: 'stopped' },
  workloads: {
    'rppg': { status: 'idle', eventCount: 0, lastEventTime: null, latestData: {} },
    'ai-ecg': { status: 'idle', eventCount: 0, lastEventTime: null, latestData: {} },
    'mdpnp': { status: 'idle', eventCount: 0, lastEventTime: null, latestData: {} },
<<<<<<< HEAD
    '3d-pose': { status: 'idle', eventCount: 0, lastEventTime: null, latestData: {}, frameData: undefined },
=======
    '3d-pose': { 
      status: 'idle', 
      eventCount: 0, 
      lastEventTime: null, 
      latestData: {}
    },
>>>>>>> dev
  },
};

const servicesSlice = createSlice({
  name: 'services',
  initialState,
  reducers: {
    setAggregatorStatus: (state, action: PayloadAction<ServicesState['aggregator']['status']>) => {
      state.aggregator.status = action.payload;
    },

<<<<<<< HEAD
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
=======
    updateWorkloadData: (state, action: PayloadAction<{
      workloadId: string;
      data: any;
      timestamp: number;
    }>) => {
      const { workloadId, data, timestamp } = action.payload;

      if (!state.workloads[workloadId]) {
        state.workloads[workloadId] = {
          status: 'idle',
          eventCount: 0,
          latestData: {},
          lastEventTime: null,
        };
      }

      // Update status
      state.workloads[workloadId].status = 'running';
      state.workloads[workloadId].eventCount += 1;
      state.workloads[workloadId].lastEventTime = timestamp;

      console.log(`[Redux] 📊 Updating ${workloadId}:`, {
        eventCount: state.workloads[workloadId].eventCount,
        payloadKeys: Object.keys(data),
        hasWaveform: !!data.waveform
      });

      // Parse workload-specific data
      if (workloadId === 'rppg') {
        // rPPG sends: HR, RR, SpO2, waveform
        if (data.HR !== undefined) state.workloads[workloadId].latestData.HR = data.HR;
        if (data.RR !== undefined) state.workloads[workloadId].latestData.RR = data.RR;
        if (data.SpO2 !== undefined) state.workloads[workloadId].latestData.SpO2 = data.SpO2;

        if (data.waveform && Array.isArray(data.waveform)) {
          state.workloads[workloadId].waveform = data.waveform;
          console.log(`[Redux] ✓ rPPG waveform: ${data.waveform.length} samples`);
        }

        console.log(`[Redux] ✓ rPPG vitals: HR=${state.workloads[workloadId].latestData.HR}, RR=${state.workloads[workloadId].latestData.RR}, SpO2=${state.workloads[workloadId].latestData.SpO2}`);
      } else if (workloadId === 'ai-ecg') {
        // AI-ECG sends: prediction, filename, waveform, waveformFrequency
        if (data.prediction !== undefined) {
          state.workloads[workloadId].latestData.prediction = data.prediction;
          console.log(`[Redux] ✓ AI-ECG prediction: ${data.prediction}`);
        }

        if (data.filename !== undefined) {
          state.workloads[workloadId].latestData.filename = data.filename;
          console.log(`[Redux] ✓ AI-ECG filename: ${data.filename}`);
        }

        if (data.waveform && Array.isArray(data.waveform)) {
          state.workloads[workloadId].waveform = data.waveform;
          console.log(`[Redux] ✓ AI-ECG waveform: ${data.waveform.length} samples`);
        }

        if (data.waveformFrequency !== undefined) {
          state.workloads[workloadId].waveformFrequency = data.waveformFrequency;
          console.log(`[Redux] ✓ AI-ECG frequency: ${data.waveformFrequency} Hz`);
        }

      } else if (workloadId === 'mdpnp') {
        // MDPNP sends: HR, CO2_ET, BP_DIA, waveform with type
        if (data.HR !== undefined) {
          state.workloads[workloadId].latestData.HR = data.HR;
          console.log(`[Redux] ✓ MDPNP HR: ${data.HR}`);
        }
        if (data.CO2_ET !== undefined) {
          state.workloads[workloadId].latestData.CO2_ET = data.CO2_ET;
          console.log(`[Redux] ✓ MDPNP CO2_ET: ${data.CO2_ET}`);
        }
        if (data.BP_DIA !== undefined) {
          state.workloads[workloadId].latestData.BP_DIA = data.BP_DIA;
          console.log(`[Redux] ✓ MDPNP BP_DIA: ${data.BP_DIA}`);
        }

        if (data.waveform && Array.isArray(data.waveform)) {
          state.workloads[workloadId].waveform = data.waveform;
          state.workloads[workloadId].waveformType = data.waveformType || 'unknown';
          console.log(`[Redux] ✓ MDPNP ${state.workloads[workloadId].waveformType} waveform: ${data.waveform.length} samples`);
        }

      } else if (workloadId === '3d-pose') {
        // ✅ 3D Pose sends: joints array, activity, num_persons
        
        // Store joints array for 3D visualization
        if (data.joints && Array.isArray(data.joints)) {
          state.workloads[workloadId].joints = data.joints;
          console.log(`[Redux] ✓ 3D Pose joints array: ${data.joints.length} joints stored`);
        }
        
        // Store activity for display
        if (data.activity !== undefined) {
          state.workloads[workloadId].latestData.activity = data.activity;
          console.log(`[Redux] ✓ 3D Pose activity: ${data.activity}`);
        }
        
        // Store number of persons detected
        if (data.num_persons !== undefined) {
          state.workloads[workloadId].latestData.num_persons = data.num_persons;
          console.log(`[Redux] ✓ 3D Pose persons detected: ${data.num_persons}`);
        }
        
        // Store frame number
        if (data.frame_number !== undefined) {
          state.workloads[workloadId].latestData.frame_number = data.frame_number;
        }
        
        // Store all people data
        if (data.people && Array.isArray(data.people)) {
          state.workloads[workloadId].people = data.people;
          console.log(`[Redux] ✓ 3D Pose people array: ${data.people.length} people stored`);
        }
        
        // Debug: Show first joint if available
        if (data.joints && data.joints.length > 0) {
          console.log(`[Redux] 📍 First joint:`, data.joints[0]);
        }
      }
    },

    resetWorkloadData: (state, action: PayloadAction<keyof ServicesState['workloads']>) => {
>>>>>>> dev
      const workloadId = action.payload;
      state.workloads[workloadId] = {
        status: 'idle',
        eventCount: 0,
        lastEventTime: null,
        latestData: {},
<<<<<<< HEAD
      };
=======
        waveform: undefined,
        joints: undefined,  // ✅ Add this
        people: undefined,  // ✅ Add this
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
>>>>>>> dev
    },
  },
});

<<<<<<< HEAD
export const { setAggregatorStatus, updateWorkloadData, resetWorkloadData, startAllWorkloads,
  stopAllWorkloads, } = servicesSlice.actions;
=======
export const {
  setAggregatorStatus,
  updateWorkloadData,
  resetWorkloadData,
  startAllWorkloads,
  stopAllWorkloads,
} = servicesSlice.actions;

>>>>>>> dev
export default servicesSlice.reducer;