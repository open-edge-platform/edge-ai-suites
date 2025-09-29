import { createSlice} from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';

interface TranscriptState {
  streamingText: string;
  finalText: string | null;
  status: 'idle' | 'streaming' | 'done';
}
const initialState: TranscriptState = { streamingText: '', finalText: null, status: 'idle' };

const transcriptSlice = createSlice({
  name: 'transcript',
  initialState,
  reducers: {
    resetTranscript: () => initialState,
    startTranscript(state) { state.status = 'streaming'; state.streamingText = ''; state.finalText = null; },
    appendTranscript(state, action: PayloadAction<string>) { state.streamingText += action.payload; },
    finishTranscript(state) { state.finalText = state.streamingText; state.status = 'done'; },
  },
});

export const { resetTranscript, startTranscript, appendTranscript, finishTranscript } = transcriptSlice.actions;
export default transcriptSlice.reducer;