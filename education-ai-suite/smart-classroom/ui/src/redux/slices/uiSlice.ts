import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
 
export type Tab = 'transcripts' | 'summary' | 'mindmap';
export type ProcessingMode = 'audio' | 'video-only' | 'microphone' | null;
export type AudioStatus = 'idle' | 'checking' | 'ready' | 'recording' | 'processing' | 'transcribing' | 'summarizing' | 'mindmapping' | 'complete' | 'error' | 'no-devices';
export type VideoStatus = 'idle' | 'ready' | 'starting' | 'streaming' | 'stopping' | 'failed' | 'completed' | 'no-config'| 'playback';

export interface SearchResult {
  score: number;
  session_id: string;
  topic: string;
  start_time: number;
  end_time: number;
  text: string;
}
 
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
  monitoringActive: boolean;
  monitoringPaused: boolean;
  videoPlaybackMode: boolean;
  uploadedVideoFiles: {
    front: File | null;
    back: File | null;
    board: File | null;
  };
  recordedVideoType: 'back' | 'board' | 'front' | null;
  searchQuery: string;
  searchResults: SearchResult[];
  showSearchResults: boolean; 
  contentSegmentationStatus: 'idle' | 'loading' | 'complete' | 'error';
  contentSegmentationEnabled: boolean;
  searchLoading: boolean;
  searchError: string | null;
  contentSegmentationError: string | null;
  timelineHighlight: {
    startTime: number;
    endTime: number;
    topic: string;
  } | null;
  csProcessing: boolean;
  transcriptionDone: boolean;
  csUploadsComplete: boolean;
  csHasUploads: boolean;
  csTags: string[];
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
  transcriptionDone: false,
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
  monitoringActive: false,
  monitoringPaused: false,
  videoPlaybackMode: false,
  uploadedVideoFiles: {
    front: null,
    back: null,
    board: null,
  },
  recordedVideoType: null,
  searchQuery: '',
  searchResults: [],
  showSearchResults: false, 
  contentSegmentationStatus: 'idle',
  contentSegmentationEnabled: false,
  searchLoading: false,
  searchError: null,
  contentSegmentationError: null,
  timelineHighlight: null,
  csProcessing: false,
  csUploadsComplete: false,
  csHasUploads: false,
  csTags: [],
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
      state.transcriptionDone = false;
      state.videoAnalyticsLoading = false;
      state.videoAnalyticsActive = false;
      state.contentSegmentationStatus = 'idle';
      state.contentSegmentationEnabled = false;
      state.contentSegmentationError = null;
      state.searchLoading = false;
      state.searchError = null;
      state.searchQuery = '';
      state.searchResults = [];
      state.showSearchResults = false;
      state.timelineHighlight = null;
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
      state.contentSegmentationStatus = 'idle';
      state.contentSegmentationEnabled = false;
      state.contentSegmentationError = null;
      state.searchLoading = false;
      state.searchError = null;
    },
 
    transcriptionComplete(state) {
      console.log('transcriptionComplete reducer called');
      state.transcriptionDone = true;
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
      state.mindmapLoading = false;
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
      state.videoStatus = 'completed';
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
      } else if (!state.videoAnalyticsLoading && state.videoStatus !== 'completed') {
        state.videoStatus = 'ready';
      }
    },

    setProcessingMode(state, action: PayloadAction<ProcessingMode>) {
      state.processingMode = action.payload;
    },

    loadCameraSettingsFromStorage(state) {
      const hasVideoConfig = Boolean(
        state.frontCamera?.trim() ||
        state.backCamera?.trim() ||
        state.boardCamera?.trim()
      );
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

    setMonitoringActive: (state, action) => {
      state.monitoringActive = action.payload;
    },

    setMonitoringPaused: (state, action: PayloadAction<boolean>) => {
      state.monitoringPaused = action.payload;
    },
    
    setUploadedVideoFiles(state, action: PayloadAction<{
      front?: File | null;
      back?: File | null;
      board?: File | null;
    }>) {
      if (action.payload.front !== undefined) {
        state.uploadedVideoFiles.front = action.payload.front;
      }
      if (action.payload.back !== undefined) {
        state.uploadedVideoFiles.back = action.payload.back;
      }
      if (action.payload.board !== undefined) {
        state.uploadedVideoFiles.board = action.payload.board;
      }
    },

    setVideoPlaybackMode(state, action: PayloadAction<boolean>) {
      state.videoPlaybackMode = action.payload;
    },
    
    setRecordedVideoType(state, action: PayloadAction<'back' | 'board' | 'front' | null>) {
      state.recordedVideoType = action.payload;
    },
    
    setPlaybackFromUploads(state) {
      const hasFiles =
        state.uploadedVideoFiles.front ||
        state.uploadedVideoFiles.back ||
        state.uploadedVideoFiles.board;
      if (hasFiles) {
        state.videoStatus = "completed";
      }
    },

    setContentSegmentationStatus(state, action: PayloadAction<'idle' | 'loading' | 'complete' | 'error' >) {
      state.contentSegmentationStatus = action.payload;
    },

    setContentSegmentationEnabled(state, action: PayloadAction<boolean>) {
      state.contentSegmentationEnabled = action.payload;
    },

    startContentSegmentation(state) {
      state.contentSegmentationStatus = 'loading';
      state.contentSegmentationEnabled = false;
    },

    contentSegmentationSuccess(state) {
      state.contentSegmentationStatus = 'complete';
      state.contentSegmentationEnabled = true;
    },

    contentSegmentationFailed(state, action: PayloadAction<string | undefined>) {
      state.contentSegmentationStatus = 'error';
      state.contentSegmentationEnabled = false;
      state.contentSegmentationError = action.payload || 'Content preparation failed. Please try again.';
    },

    setSearchLoading(state, action: PayloadAction<boolean>) {
      state.searchLoading = action.payload;
    },

    setSearchError(state, action: PayloadAction<string | null>) {
      state.searchError = action.payload;
    },
    
    setSearchQuery(state, action: PayloadAction<string>) {
      state.searchQuery = action.payload;
    },

    setSearchResults(state, action: PayloadAction<SearchResult[]>) {
      state.searchResults = action.payload;
      state.showSearchResults = action.payload.length > 0;
    },

    setShowSearchResults(state, action: PayloadAction<boolean>) {
      state.showSearchResults = action.payload;
    },

    setTimelineHighlight(state, action: PayloadAction<{
      startTime: number;
      endTime: number;
      topic: string;
    } | null>) {
      state.timelineHighlight = action.payload;
    },

    setCsProcessing(state, action: PayloadAction<boolean>) {
      state.csProcessing = action.payload;
    },

    setCsUploadsComplete(state, action: PayloadAction<boolean>) {
      state.csUploadsComplete = action.payload;
    },

    setCsHasUploads(state, action: PayloadAction<boolean>) {
      state.csHasUploads = action.payload;
    },

    setCsTags(state, action: PayloadAction<string[]>) {
      state.csTags = action.payload;
    },

    clearSearchResults(state) {
      state.searchResults = [];
      state.showSearchResults = false;
      state.timelineHighlight = null;
      state.searchQuery = '';
    },

    resetFlow(state) {
      const preservedAudioDevices = state.hasAudioDevices;
      const preservedAudioDevicesLoading = state.audioDevicesLoading;
      const preservedCsHasUploads = state.csHasUploads;
      const preservedCsUploadsComplete = state.csUploadsComplete;
      Object.assign(state, initialState);
      state.hasAudioDevices = preservedAudioDevices;
      state.audioDevicesLoading = preservedAudioDevicesLoading;
      state.csHasUploads = preservedCsHasUploads;
      state.csUploadsComplete = preservedCsUploadsComplete;
      state.audioStatus = preservedAudioDevicesLoading ? 'checking' : (preservedAudioDevices ? 'ready' : 'no-devices');
      state.contentSegmentationStatus = 'idle';
      state.contentSegmentationEnabled = false;
      state.contentSegmentationError = null;
      state.searchLoading = false;
      state.searchError = null;
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
  setMonitoringActive,
  setMonitoringPaused,
  setUploadedVideoFiles,
  setVideoPlaybackMode,
  setRecordedVideoType,
  setPlaybackFromUploads,
  setContentSegmentationStatus,
  setContentSegmentationEnabled,
  startContentSegmentation,
  contentSegmentationSuccess,
  contentSegmentationFailed,
  setSearchLoading,
  setSearchError,
  setSearchQuery,
  setSearchResults,
  clearSearchResults,
  setShowSearchResults,
  setTimelineHighlight,
  setCsProcessing,
  setCsUploadsComplete,
  setCsHasUploads,
  setCsTags,
} = uiSlice.actions;
 
export default uiSlice.reducer;