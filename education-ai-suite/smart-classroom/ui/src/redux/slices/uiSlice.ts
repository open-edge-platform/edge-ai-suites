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
  frontCamera: string;
  backCamera: string;
  boardCamera: string;
  frontCameraStream: string;
  backCameraStream: string;
  boardCameraStream: string;
  activeStream: 'front' | 'back' | 'content' | 'all' | null;
  videoAnalyticsLoading: boolean;
  videoAnalyticsActive: boolean;
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
  activeStream: null,
  frontCamera: '', // Empty string as default for text input
  backCamera: '', // Empty string as default for text input
  boardCamera: '', // Empty string as default for text input
  frontCameraStream: '',
  backCameraStream: '',
  boardCameraStream: '',
  videoAnalyticsLoading: false,
  videoAnalyticsActive: false,
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
      state.videoAnalyticsLoading = false;
      state.videoAnalyticsActive = false;
    },
 
    processingFailed(state) {
      state.aiProcessing = false;
      state.summaryLoading = false;
      state.mindmapLoading = false;
      state.videoAnalyticsLoading = false;
      state.videoAnalyticsActive = false;
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
    
    setActiveStream(state, action: PayloadAction<'front' | 'back' | 'content' | 'all' | null>) {
      state.activeStream = action.payload;
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
    
    setFrontCamera(state, action: PayloadAction<string>) {
      state.frontCamera = action.payload;
    },
    
    setBackCamera(state, action: PayloadAction<string>) {
      state.backCamera = action.payload;
    },
    
    setBoardCamera(state, action: PayloadAction<string>) {
      state.boardCamera = action.payload;
    },
    
    setFrontCameraStream(state, action: PayloadAction<string>) {
      state.frontCameraStream = action.payload;
    },
    
    setBackCameraStream(state, action: PayloadAction<string>) {
      state.backCameraStream = action.payload;
    },
    
    setBoardCameraStream(state, action: PayloadAction<string>) {
      state.boardCameraStream = action.payload;
    },
    
    resetStream(state) {
      state.activeStream = null;
      // Don't reset camera values when resetting stream
    },
 
    startStream(state) {
      state.activeStream = 'all';
    },
 
    stopStream(state) {
      state.activeStream = null;
    },
 
    setVideoAnalyticsLoading(state, action: PayloadAction<boolean>) {
      state.videoAnalyticsLoading = action.payload;
    },

    setVideoAnalyticsActive(state, action: PayloadAction<boolean>) {
      state.videoAnalyticsActive = action.payload;
    },

    loadCameraSettingsFromStorage(state) {
      const frontCamera = localStorage.getItem('frontCamera');
      const backCamera = localStorage.getItem('backCamera');
      const boardCamera = localStorage.getItem('boardCamera');
      
      if (frontCamera) state.frontCamera = frontCamera;
      if (backCamera) state.backCamera = backCamera;
      if (boardCamera) state.boardCamera = boardCamera;
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
  setActiveStream,
  resetStream,
  startStream,
  stopStream,
  firstSummaryToken,
  summaryDone,
  mindmapStart,
  mindmapSuccess,
  mindmapFailed,
  clearMindmapStartRequest,
  setActiveTab,
  setProjectLocation,
  resetFlow,
  setFrontCamera, 
  setBackCamera, 
  setBoardCamera,
  setFrontCameraStream,
  setBackCameraStream,
  setBoardCameraStream,
  setVideoAnalyticsLoading,
  setVideoAnalyticsActive,
  loadCameraSettingsFromStorage,
} = uiSlice.actions;
 
export default uiSlice.reducer;