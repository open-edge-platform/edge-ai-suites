import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

interface MindmapState {
  streamingText: string;
  finalText: string | null;
  isStreaming: boolean;
  isRendered: boolean;
  svg: string | null;
  generationTime: number | null; 
}

const initialState: MindmapState = {
  streamingText: "",
  finalText: null,
  isStreaming: false,
  isRendered: false,
  svg: null,
  generationTime: null,
};

const mindmapSlice = createSlice({
  name: "mindmap",
  initialState,
  reducers: {
    startMindmap: (state) => {
      state.streamingText = "";
      state.finalText = null;
      state.isStreaming = true;
      state.isRendered = false;
      state.generationTime = null; 
    },
    appendMindmap: (state, action: PayloadAction<string>) => {
      state.streamingText = action.payload;
    },
    finishMindmap: (state) => {
      state.finalText = state.streamingText;
      state.isStreaming = false;
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
    clearMindmap: (state) => {
      state.streamingText = "";
      state.finalText = null;
      state.isStreaming = false;
      state.isRendered = false;
      state.svg = null;
      state.generationTime = null;
    },
  },
});

export const {
  startMindmap,
  appendMindmap,
  finishMindmap,
  setRendered,
  setSVG,
  setGenerationTime, 
  clearMindmap,
} = mindmapSlice.actions;

export default mindmapSlice.reducer;
