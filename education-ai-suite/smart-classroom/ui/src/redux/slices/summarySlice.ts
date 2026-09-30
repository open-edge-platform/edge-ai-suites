import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';

export interface SummaryProgress {
  stage: string;
  chunk: number;
  chunks: number;
}

interface SummaryState {
  streamingText: string;
  finalText: string | null;
  status: 'idle' | 'streaming' | 'done';
  // Where a long, chunked summary has got to, and whether the board OCR input
  // was only partially available. The stream that reports both runs outside
  // AISummaryTab (see useAudioPipeline), so they live here instead of in the
  // tab's local state.
  progress: SummaryProgress | null;
  boardOcrPartial: boolean;
}
const initialState: SummaryState = {
  streamingText: '',
  finalText: null,
  status: 'idle',
  progress: null,
  boardOcrPartial: false,
};

const summarySlice = createSlice({
  name: 'summary',
  initialState,
  reducers: {
    resetSummary: () => initialState, // <-- resets status to 'idle'
    startSummary(state) {
      state.status = 'streaming';
      state.streamingText = '';
      state.finalText = null;
      state.progress = null;
      state.boardOcrPartial = false;
    },
    appendSummary(state, action: PayloadAction<string>) {
      state.streamingText += action.payload;
      // Tokens are the summary itself, so per-chunk progress is over.
      state.progress = null;
    },
    finishSummary(state) {
      state.finalText = state.streamingText;
      state.status = 'done';
      state.progress = null;
    },
    setSummaryProgress(state, action: PayloadAction<SummaryProgress>) {
      state.progress = action.payload;
    },
    setBoardOcrPartial(state, action: PayloadAction<boolean>) {
      state.boardOcrPartial = action.payload;
    },
  },
});

export const {
  resetSummary,
  startSummary,
  appendSummary,
  finishSummary,
  setSummaryProgress,
  setBoardOcrPartial,
} = summarySlice.actions;
export default summarySlice.reducer;
