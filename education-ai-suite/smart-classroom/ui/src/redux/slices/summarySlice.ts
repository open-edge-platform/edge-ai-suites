import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';

interface SummaryState {
  streamingText: string;
  finalText: string | null;
  status: 'idle' | 'streaming' | 'done';
}
const initialState: SummaryState = { streamingText: '', finalText: null, status: 'idle' };

const summarySlice = createSlice({
  name: 'summary',
  initialState,
  reducers: {
    resetSummary: () => initialState, // <-- resets status to 'idle'
    startSummary(state) { state.status = 'streaming'; state.streamingText = ''; state.finalText = null; },
    appendSummary(state, action: PayloadAction<string>) { state.streamingText += action.payload; },
    finishSummary(state) { state.finalText = state.streamingText; state.status = 'done'; },
  },
});

export const { resetSummary, startSummary, appendSummary, finishSummary } = summarySlice.actions;
export default summarySlice.reducer;