import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

interface MindmapState {
  finalText: string | null;
  isLoading: boolean;
  isRendered: boolean;
  svg: string | null;
  generationTime: number | null;
  error: string | null;
  sessionId: string | null;
  // performance.now() when the fetch was kicked off, so MindMapTab can report
  // generation time (fetch through first render) even though the fetch itself
  // is driven from outside the tab (see useAudioPipeline).
  startedAt: number | null;
}

const initialState: MindmapState = {
  finalText: null,
  isLoading: false,
  isRendered: false,
  svg: null,
  generationTime: null,
  error: null,
  sessionId: null,
  startedAt: null,
};

const mindmapSlice = createSlice({
  name: "mindmap",
  initialState,
  reducers: {
    startMindmap: (state, action: PayloadAction<{ sessionId: string; startedAt: number }>) => {
      const { sessionId, startedAt } = action.payload;
      console.log('🧠 Starting mindmap for session:', sessionId);
      if (state.sessionId !== sessionId) {
        state.isLoading = true;
        state.isRendered = false;
        state.finalText = null;
        state.svg = null;
        state.generationTime = null;
        state.error = null;
        state.sessionId = sessionId;
        state.startedAt = startedAt;
      }
    },
    
    setMindmap: (state, action: PayloadAction<string>) => {
      state.finalText = action.payload;
      state.isLoading = false;
      state.error = null;
    },
    
    setRendered: (state, action: PayloadAction<boolean>) => {
      state.isRendered = action.payload;
    },
    
    setSVG: (state, action: PayloadAction<string>) => {
      state.svg = action.payload;
    },
    
    setGenerationTime: (state, action: PayloadAction<number>) => {
      state.generationTime = action.payload;
    },
    
    setError: (state, action: PayloadAction<string>) => {
      state.error = action.payload;
      state.isLoading = false;
    },
    
    clearMindmap: () => {
      return initialState;
    },
  },
});

export const {
  startMindmap,
  setMindmap,
  setRendered,
  setSVG,
  setGenerationTime,
  setError,
  clearMindmap,
} = mindmapSlice.actions;

export default mindmapSlice.reducer;