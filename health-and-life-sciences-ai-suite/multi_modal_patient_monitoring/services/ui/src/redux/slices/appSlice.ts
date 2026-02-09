// src/redux/slices/appSlice.ts
import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';

interface AppState {
  projectName: string;
  isProcessing: boolean;
  isLocked: boolean;
  lockReason: string | null;
  expandedWorkload: string | null;
}

const initialState: AppState = {
  projectName: 'Health AI Suite',
  isProcessing: false, // Change to true to test "processing" UI
  isLocked: false,
  lockReason: null,
  expandedWorkload: null,
};


const appSlice = createSlice({
  name: 'app',
  initialState,
  reducers: {
    setProjectName: (state, action: PayloadAction<string>) => {
      state.projectName = action.payload;
    },
    startProcessing: (state) => {
      state.isProcessing = true;
    },
    stopProcessing: (state) => {
      state.isProcessing = false;
    },
    setStreamingLock: (state, action: PayloadAction<{ locked: boolean; reason?: string }>) => {
      state.isLocked = action.payload.locked;
      state.lockReason = action.payload.reason || null;
    },
    setExpandedWorkload: (state, action: PayloadAction<string | null>) => { // Add this reducer
      state.expandedWorkload = action.payload;
    },
  },
});

export const { setProjectName, startProcessing, stopProcessing, setStreamingLock, setExpandedWorkload } = appSlice.actions;
export default appSlice.reducer;