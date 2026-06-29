import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

export type LifecycleState =
  | 'UNKNOWN'
  | 'INITIALIZING'
  | 'PREPARING'
  | 'READY'
  | 'STARTING'
  | 'RUNNING'
  | 'STOPPING'
  | 'ERROR';

export interface StatusState {
  lifecycle: LifecycleState;
  buildSha: string;
  message: string;
  ready: boolean;
  /** epoch seconds */
  updatedAt: number;
}

const initialState: StatusState = {
  lifecycle: 'UNKNOWN',
  buildSha: 'dev',
  message: '',
  ready: false,
  updatedAt: 0,
};

const statusSlice = createSlice({
  name: 'status',
  initialState,
  reducers: {
    setStatus(state, action: PayloadAction<Partial<StatusState>>) {
      Object.assign(state, action.payload);
      state.updatedAt = Date.now() / 1000;
    },
    setLifecycle(state, action: PayloadAction<LifecycleState>) {
      state.lifecycle = action.payload;
      state.updatedAt = Date.now() / 1000;
    },
  },
});

export const { setStatus, setLifecycle } = statusSlice.actions;
export default statusSlice.reducer;
