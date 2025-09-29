import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';


export type Tab = 'transcripts' | 'summary';

export interface UIState {
  aiProcessing: boolean;
  summaryEnabled: boolean;
  summaryLoading: boolean;
  activeTab: Tab;
  autoSwitched: boolean;
  sessionId: string | null;
  uploadedAudioPath: string | null;
  shouldStartSummary: boolean;
  backendAvailable: boolean; 
  projectLocation: string;
}

const initialState: UIState = {
  backendAvailable: true,
  aiProcessing: false,
  summaryEnabled: false,
  summaryLoading: false,
  activeTab: 'transcripts',
  autoSwitched: false,
  sessionId: null,
  uploadedAudioPath: null,
  shouldStartSummary: false,
  projectLocation: 'storage/',
};

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setBackendAvailable(state, action: PayloadAction<boolean>) {
      state.backendAvailable = action.payload;
    },
    startProcessing(state) {
      state.aiProcessing = true;
      state.summaryEnabled = false;
      state.summaryLoading = false;
      state.activeTab = 'transcripts';
      state.autoSwitched = false;
      state.sessionId = null;
      state.uploadedAudioPath = null;
      state.shouldStartSummary = false;
    },
    processingFailed(state) {
      state.aiProcessing = false;
      state.summaryLoading = false;
    },
    transcriptionComplete(state) {
      console.log('transcriptionComplete reducer called');
      state.summaryEnabled = true;
      state.summaryLoading = true; // show spinner until first token
      state.shouldStartSummary = true; // request summary start
      if (!state.autoSwitched) {
        state.activeTab = 'summary';
        state.autoSwitched = true;
      }
    },
    clearSummaryStartRequest(state) {
      state.shouldStartSummary = false;
    },
    setUploadedAudioPath(state, action: PayloadAction<string>) {
      state.uploadedAudioPath = action.payload;
    },
    setSessionId(state, action: PayloadAction<string | null>) {
      const v = action.payload;
      if (typeof v === 'string' && v.trim().length > 0) {
        state.sessionId = v;
      }
      // ignore null/empty to avoid accidental reset
    },
    firstSummaryToken(state) {
      state.summaryLoading = false; // hide spinner on first token
    },
    summaryDone(state) {
      state.aiProcessing = false; // all done, re-enable controls
    },
    setActiveTab(state, action: PayloadAction<Tab>) {
      state.activeTab = action.payload;
    },
    setProjectLocation(state, action: PayloadAction<string>) { // Add reducer to update projectLocation
      state.projectLocation = action.payload;},
    resetFlow() {
      return initialState;
    },
  },
});

export const {
  setBackendAvailable,
  startProcessing,
  processingFailed,
  transcriptionComplete,
  clearSummaryStartRequest,
  setUploadedAudioPath,
  setSessionId,
  firstSummaryToken,
  summaryDone,
  setActiveTab,
  setProjectLocation,
  resetFlow,
} = uiSlice.actions;

export default uiSlice.reducer;