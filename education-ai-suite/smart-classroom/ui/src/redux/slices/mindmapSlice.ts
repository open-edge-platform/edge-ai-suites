import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

interface MindmapState {
  finalText: string | null;
  isLoading: boolean;
  isRendered: boolean;
  svg: string | null;
  generationTime: number | null;
  error: string | null;
  sessionId: string | null;
}

const initialState: MindmapState = {
  finalText: null,
  isLoading: false,
  isRendered: false,
  svg: null,
  generationTime: null,
  error: null,
  sessionId: null,
};

const mindmapSlice = createSlice({
  name: "mindmap",
  initialState,
  reducers: {
    startMindmap: (state, action: PayloadAction<string>) => {
      console.log('🧠 Starting mindmap for session:', action.payload);
      if (state.sessionId !== action.payload) {
        state.isLoading = true;
        state.isRendered = false;
        state.finalText = null;
        state.svg = null;
        state.generationTime = null;
        state.error = null;
        state.sessionId = action.payload;
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