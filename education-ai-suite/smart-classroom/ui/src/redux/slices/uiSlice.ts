import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
 
export type Tab = 'transcripts' | 'summary' | 'mindmap';
export type ProcessingMode = 'audio' | 'video-only' | 'microphone' | null;
export type AudioStatus = 'idle' | 'checking' | 'ready' | 'recording' | 'processing' | 'transcribing' | 'summarizing' | 'mindmapping' | 'complete' | 'error' | 'no-devices';
export type VideoStatus = 'idle' | 'ready' | 'starting' | 'streaming' | 'stopping' | 'failed' | 'complete' | 'no-config';
 
export interface UIState {
  aiProcessing: boolean;
  summaryEnabled: boolean;
  summaryLoading: boolean;
  summaryComplete: boolean;
  mindmapEnabled: boolean;
  mindmapLoading: boolean;
  activeTab: Tab;
  autoSwitched: boolean;
  autoSwitchedToMindmap: boolean;
  sessionId: string | null;
  videoSessionId: string | null;
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
  processingMode: ProcessingMode;
  audioStatus: AudioStatus;
  videoStatus: VideoStatus;
  hasAudioDevices: boolean;
  audioDevicesLoading: boolean;
  isRecording: boolean;
  justStoppedRecording: boolean;
  videoAnalyticsStopping: boolean;
  hasUploadedVideoFiles: boolean;
}
 
const initialState: UIState = {
  aiProcessing: false,
  summaryEnabled: false,
  summaryLoading: false,
  summaryComplete: false,
  mindmapEnabled: false,
  mindmapLoading: false,
  activeTab: 'transcripts',
  autoSwitched: false,
  autoSwitchedToMindmap: false,
  sessionId: null,
  videoSessionId: null,
  uploadedAudioPath: null,
  shouldStartSummary: false,
  shouldStartMindmap: false,
  projectLocation: 'storage/',
  activeStream: null,
  frontCamera: '',
  backCamera: '',
  boardCamera: '',
  frontCameraStream: '',
  backCameraStream: '',
  boardCameraStream: '',
  videoAnalyticsLoading: false,
  videoAnalyticsActive: false,
  processingMode: null,
  audioStatus: 'idle',
  videoStatus: 'idle',
  hasAudioDevices: true,
  audioDevicesLoading: false,
  isRecording: false,
  justStoppedRecording: false,
  videoAnalyticsStopping: false,
  hasUploadedVideoFiles: false,
};
 
const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    startProcessing(state) {
      state.aiProcessing = true;
      state.summaryEnabled = false;
      state.summaryLoading = false;
      state.summaryComplete = false;
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
      state.summaryComplete = false;
      state.mindmapLoading = false;
      state.videoAnalyticsLoading = false;
      state.videoAnalyticsActive = false;
      state.processingMode = null;
      state.audioStatus = 'error';
      state.videoStatus = 'failed';
      state.isRecording = false;
      state.videoAnalyticsStopping = false;
    },
 
    transcriptionComplete(state) {
      console.log('transcriptionComplete reducer called');
      state.summaryEnabled = true;
      state.summaryLoading = true;
      state.summaryComplete = false;
      state.shouldStartSummary = true;
      state.audioStatus = 'summarizing';
      if (!state.autoSwitched) {
        state.activeTab = 'summary';
        state.autoSwitched = true;
      }
    },
 
    clearSummaryStartRequest(state) {
      state.shouldStartSummary = false;
    },

    summaryStreamComplete(state) {
      state.summaryLoading = false;
      state.summaryComplete = true;
      state.audioStatus = 'summarizing';
      console.log('🎯 Summary stream completed');
    },
 
    setUploadedAudioPath(state, action: PayloadAction<string>) {
      state.uploadedAudioPath = action.payload;
      if (action.payload === 'MICROPHONE') {
        state.audioStatus = 'recording';
      } else if (action.payload && action.payload !== '') {
        state.audioStatus = 'processing';
      }
    },
 
    setSessionId(state, action: PayloadAction<string | null>) {
      const v = action.payload;
      if (typeof v === 'string' && v.trim().length > 0) {
        state.sessionId = v;
      }
    },

    setVideoSessionId(state, action: PayloadAction<string | null>) {
      state.videoSessionId = action.payload;
    },
    
    setActiveStream(state, action: PayloadAction<'front' | 'back' | 'content' | 'all' | null>) {
      state.activeStream = action.payload;
    },
    
    firstSummaryToken(state) {
      state.summaryLoading = false;
      state.audioStatus = 'summarizing';
    },
 
    summaryDone(state) {
      state.aiProcessing = false;
      state.summaryComplete = true;
      state.mindmapEnabled = true;
      state.mindmapLoading = true;
      state.shouldStartMindmap = true;
      state.audioStatus = 'mindmapping';
 
      if (!state.autoSwitchedToMindmap) {
        state.activeTab = 'mindmap';
        state.autoSwitchedToMindmap = true;
      }
    },
   
    mindmapStart(state) {
      state.mindmapLoading = true;
      state.shouldStartMindmap = true;
      state.audioStatus = 'mindmapping';
    },
 
    mindmapSuccess(state) {
      state.mindmapLoading = false;
      state.shouldStartMindmap = false;
      state.audioStatus = 'complete';
    },
 
    mindmapFailed(state) {
      state.mindmapLoading = false;
      state.shouldStartMindmap = false;
      state.audioStatus = 'error';
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
      state.videoStatus = 'idle';
    },
 
    startStream(state) {
      state.activeStream = 'all';
      state.videoStatus = 'streaming';
    },
 
    stopStream(state) {
      state.activeStream = null;
      state.videoStatus = 'complete';
    },
 
    setVideoAnalyticsLoading(state, action: PayloadAction<boolean>) {
      state.videoAnalyticsLoading = action.payload;
      if (action.payload) {
        state.videoStatus = 'starting';
      }
    },

    setVideoAnalyticsActive(state, action: PayloadAction<boolean>) {
      state.videoAnalyticsActive = action.payload;
      if (action.payload) {
        state.videoStatus = 'streaming';
        state.videoAnalyticsLoading = false;
      } else if (!state.videoAnalyticsLoading) {
        state.videoStatus = 'ready';
      }
    },

    setProcessingMode(state, action: PayloadAction<ProcessingMode>) {
      state.processingMode = action.payload;
    },

    loadCameraSettingsFromStorage(state) {
      const frontCamera = localStorage.getItem('frontCamera');
      const backCamera = localStorage.getItem('backCamera');
      const boardCamera = localStorage.getItem('boardCamera');
      
      if (frontCamera) state.frontCamera = frontCamera;
      if (backCamera) state.backCamera = backCamera;
      if (boardCamera) state.boardCamera = boardCamera;
      
      const hasVideoConfig = Boolean(frontCamera?.trim() || backCamera?.trim() || boardCamera?.trim());
      state.videoStatus = hasVideoConfig ? 'ready' : 'no-config';
    },

    setAudioStatus(state, action: PayloadAction<AudioStatus>) {
      state.audioStatus = action.payload;
    },

    setVideoStatus(state, action: PayloadAction<VideoStatus>) {
      state.videoStatus = action.payload;
    },

    setHasAudioDevices(state, action: PayloadAction<boolean>) {
      state.hasAudioDevices = action.payload;
      state.audioStatus = action.payload ? 'ready' : 'no-devices';
    },

    setAudioDevicesLoading(state, action: PayloadAction<boolean>) {
      state.audioDevicesLoading = action.payload;
      if (action.payload) {
        state.audioStatus = 'checking';
      }
    },

    setIsRecording(state, action: PayloadAction<boolean>) {
      state.isRecording = action.payload;
      if (action.payload) {
        state.justStoppedRecording = false;
        if (state.hasAudioDevices) {
          state.audioStatus = 'recording';
        }
        if (state.videoStatus === 'ready') {
          state.videoStatus = 'starting';
        }
      } else {
        state.justStoppedRecording = true;
      }
    },

    setJustStoppedRecording(state, action: PayloadAction<boolean>) {
      state.justStoppedRecording = action.payload;
    },

    setVideoAnalyticsStopping(state, action: PayloadAction<boolean>) {
      state.videoAnalyticsStopping = action.payload;
      if (action.payload) {
        state.videoStatus = 'stopping';
      }
    },

    startTranscription(state) {
      state.audioStatus = 'transcribing';
    },

    setHasUploadedVideoFiles(state, action: PayloadAction<boolean>) {
      state.hasUploadedVideoFiles = action.payload;
      if (action.payload && state.videoStatus === 'no-config') {
        state.videoStatus = 'ready';
      }
    },
    
    resetFlow(state) {
      const preservedAudioDevices = state.hasAudioDevices;
      const preservedAudioDevicesLoading = state.audioDevicesLoading;
      const preservedHasUploadedVideoFiles = state.hasUploadedVideoFiles;
      const preservedCameras = {
        frontCamera: state.frontCamera,
        backCamera: state.backCamera,
        boardCamera: state.boardCamera,
      };
      
      Object.assign(state, initialState);
      
      state.hasAudioDevices = preservedAudioDevices;
      state.audioDevicesLoading = preservedAudioDevicesLoading;
      state.hasUploadedVideoFiles = preservedHasUploadedVideoFiles;
      state.frontCamera = preservedCameras.frontCamera;
      state.backCamera = preservedCameras.backCamera;
      state.boardCamera = preservedCameras.boardCamera;
      
      state.audioStatus = preservedAudioDevicesLoading ? 'checking' : (preservedAudioDevices ? 'ready' : 'no-devices');
      const hasVideoConfig = Boolean(preservedCameras.frontCamera?.trim() || preservedCameras.backCamera?.trim() || preservedCameras.boardCamera?.trim() || preservedHasUploadedVideoFiles);
      state.videoStatus = hasVideoConfig ? 'ready' : 'no-config';
    },
  },
});
 
export const {
  startProcessing,
  processingFailed,
  transcriptionComplete,
  clearSummaryStartRequest,
  summaryStreamComplete, 
  setUploadedAudioPath,
  setSessionId,
  setVideoSessionId,
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
  setProcessingMode,
  loadCameraSettingsFromStorage,
  setAudioStatus,
  setVideoStatus,
  setHasAudioDevices,
  setAudioDevicesLoading,
  setIsRecording,
  setJustStoppedRecording,
  setVideoAnalyticsStopping,
  startTranscription,
  setHasUploadedVideoFiles,
} = uiSlice.actions;
 
export default uiSlice.reducer;