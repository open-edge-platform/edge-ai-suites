import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

export type Device = 'CPU' | 'GPU' | 'NPU';
export type Source = 'file' | 'basler';

export interface ControlState {
  device: Device;
  source: Source;
  threshold: number;
  modelName: string;
  inflightAction: 'idle' | 'starting' | 'stopping';
  lastError: string | null;
}

const initialState: ControlState = {
  device: 'GPU',
  source: 'file',
  threshold: 0.5,
  modelName: 'yolo11n_polyp',
  inflightAction: 'idle',
  lastError: null,
};

const controlSlice = createSlice({
  name: 'control',
  initialState,
  reducers: {
    setDevice(state, action: PayloadAction<Device>) {
      state.device = action.payload;
    },
    setSource(state, action: PayloadAction<Source>) {
      state.source = action.payload;
    },
    setThreshold(state, action: PayloadAction<number>) {
      state.threshold = action.payload;
    },
    setInflight(state, action: PayloadAction<ControlState['inflightAction']>) {
      state.inflightAction = action.payload;
    },
    setLastError(state, action: PayloadAction<string | null>) {
      state.lastError = action.payload;
    },
  },
});

export const { setDevice, setSource, setThreshold, setInflight, setLastError } = controlSlice.actions;
export default controlSlice.reducer;
