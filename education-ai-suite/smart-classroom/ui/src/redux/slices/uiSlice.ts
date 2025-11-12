import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

export type Tab = 'transcripts' | 'summary' | 'mindmap';

export interface UIState {
  aiProcessing: boolean;
  summaryEnabled: boolean;
  summaryLoading: boolean;
  mindmapEnabled: boolean;
  mindmapLoading: boolean;
  activeTab: Tab;
  autoSwitched: boolean;
  autoSwitchedToMindmap: boolean;
  sessionId: string | null;
  uploadedAudioPath: string | null;
  shouldStartSummary: boolean;
  shouldStartMindmap: boolean;
  projectLocation: string;
}

const initialState: UIState = {
  aiProcessing: false,
  summaryEnabled: false,
  summaryLoading: false,
  mindmapEnabled: false,
  mindmapLoading: false,
  activeTab: 'transcripts',
  autoSwitched: false,
  autoSwitchedToMindmap: false,
  sessionId: null,
  uploadedAudioPath: null,
  shouldStartSummary: false,
  shouldStartMindmap: false,
  projectLocation: 'storage/',
};

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    startProcessing(state) {
      state.aiProcessing = true;
      state.summaryEnabled = false;
      state.summaryLoading = false;
      state.mindmapEnabled = false;
      state.mindmapLoading = false;
      state.activeTab = 'transcripts';
      state.autoSwitched = false;
      state.autoSwitchedToMindmap = false;
      state.sessionId = null;
      state.uploadedAudioPath = null;
      state.shouldStartSummary = false;
      state.shouldStartMindmap = false;
    },

    processingFailed(state) {
      state.aiProcessing = false;
      state.summaryLoading = false;
      state.mindmapLoading = false;
    },

    transcriptionComplete(state) {
      console.log('transcriptionComplete reducer called');
      state.summaryEnabled = true;
      state.summaryLoading = true;
      state.shouldStartSummary = true;
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
    },

    firstSummaryToken(state) {
      state.summaryLoading = false; 
    },

    summaryDone(state) {
      state.aiProcessing = false;
      state.mindmapEnabled = true;
      state.mindmapLoading = true; 
      state.shouldStartMindmap = true;

      if (!state.autoSwitchedToMindmap) {
        state.activeTab = 'mindmap';
        state.autoSwitchedToMindmap = true;
      }
    },
    
    mindmapStart(state) {
      state.mindmapLoading = true;
      state.shouldStartMindmap = true;
    },

    mindmapSuccess(state) {
      state.mindmapLoading = false;
      state.shouldStartMindmap = false;
    },

    mindmapFailed(state) {
      state.mindmapLoading = false;
      state.shouldStartMindmap = false;
    },

    clearMindmapStartRequest(state) {
      state.shouldStartMindmap = false;
    },

    setActiveTab(state, action: PayloadAction<Tab>) {
      state.activeTab = action.payload;
    },

    setProjectLocation(state, action: PayloadAction<string>) {
      state.projectLocation = action.payload;
    },

    resetFlow() {
      return initialState;
    },
  },
});

export const {
  startProcessing,
  processingFailed,
  transcriptionComplete,
  clearSummaryStartRequest,
  setUploadedAudioPath,
  setSessionId,
  firstSummaryToken,
  summaryDone,
  mindmapStart,
  mindmapSuccess,
  mindmapFailed,
  clearMindmapStartRequest,
  setActiveTab,
  setProjectLocation,
  resetFlow,
} = uiSlice.actions;

export default uiSlice.reducer;