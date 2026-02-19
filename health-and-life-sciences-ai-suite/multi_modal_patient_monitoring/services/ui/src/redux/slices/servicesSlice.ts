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

      // ✅ Throttle 3D Pose logging (show every 30 updates ≈ once per second)
      const shouldLog = workloadId === '3d-pose' 
        ? state.workloads[workloadId].eventCount % 30 === 0
        : true;

      if (shouldLog) {
        console.log(`[Redux] 📊 Updating ${workloadId}:`, {
          eventCount: state.workloads[workloadId].eventCount,
          payloadKeys: Object.keys(data),
          hasWaveform: !!data.waveform
        });
      }

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
        if (data.BP_SYS !== undefined) {
          state.workloads[workloadId].latestData.BP_SYS = data.BP_SYS;
          console.log(`[Redux] ✓ MDPNP BP_SYS: ${data.BP_SYS}`);
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
        }
        
        // Store activity for display
        if (data.activity !== undefined) {
          state.workloads[workloadId].latestData.activity = data.activity;
        }
        
        // Store number of persons detected
        if (data.num_persons !== undefined) {
          state.workloads[workloadId].latestData.num_persons = data.num_persons;
        }
        
        // Store frame number
        if (data.frame_number !== undefined) {
          state.workloads[workloadId].latestData.frame_number = data.frame_number;
        }
        
        // Store all people data
        if (data.people && Array.isArray(data.people)) {
          state.workloads[workloadId].people = data.people;
        }
        
        // Debug: Show first joint if available
        // if (data.joints && data.joints.length > 0) {
        //   console.log(`[Redux] 📍 First joint:`, data.joints[0]);
        // }
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
        workload.eventCount = 0;
        workload.lastEventTime = null;
        workload.latestData = {};
        workload.waveform = undefined;
        workload.frameData = undefined;
        workload.joints = undefined;
        workload.people = undefined;
        // optional extras used by ai-ecg / mdpnp
        (workload as any).waveformType = undefined;
        (workload as any).waveformFrequency = undefined;
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