import { createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'

export interface TranscriptSegment {
  speaker: string;
  text: string;
  start?: number;
  end?: number;
  isComplete?: boolean;
}

interface FinalEvent {
  event: 'final';
  teacher_speaker: string;
  speaker_text_stats: Record<string, number>;
}

interface TranscriptState {
  segments: TranscriptSegment[];
  status: 'idle' | 'streaming' | 'done';
  teacherSpeaker: string | null;
  speakerStats: Record<string, number>;
  currentTypingIndex: number;
  isTyping: boolean;
  shouldSwitchToSummary: boolean;
}

const initialState: TranscriptState = {
  segments: [],
  status: 'idle',
  teacherSpeaker: null,
  speakerStats: {},
  currentTypingIndex: -1,
  isTyping: false,
  shouldSwitchToSummary: false
}

const transcriptSlice = createSlice({
  name: 'transcript',
  initialState,
  reducers: {
    resetTranscript: () => initialState,

    startTranscript(state) {
      state.status = 'streaming'
      state.segments = []
      state.teacherSpeaker = null
      state.speakerStats = {}
      state.currentTypingIndex = -1
      state.isTyping = false
      state.shouldSwitchToSummary = false
    },

    appendTranscriptChunk(state, action: PayloadAction<{ text?: string, segments?: any[] }>) {
      if (action.payload.segments && action.payload.segments.length > 0) {
        for (const s of action.payload.segments) {
          state.segments.push({
            speaker: s.speaker,
            text: s.text,
            start: s.start,
            end: s.end,
            isComplete: false
          })
        }
        if (state.currentTypingIndex === -1) {
          state.currentTypingIndex = state.segments.length - action.payload.segments.length;
          state.isTyping = true;
        }
      } else if (action.payload.text) {
        const lines = action.payload.text.split('\n')
        for (const line of lines) {
          const m = line.match(/^(SPEAKER_\d+):\s*(.*)$/)
          if (m) {
            state.segments.push({ 
              speaker: m[1], 
              text: m[2],
              isComplete: false
            })
          }
        }
        if (state.currentTypingIndex === -1 && state.segments.length > 0) {
          state.currentTypingIndex = state.segments.length - lines.filter(line => 
            line.match(/^(SPEAKER_\d+):\s*(.*)$/)
          ).length;
          state.isTyping = true;
        }
      }
    },

    completeSegmentTyping(state, action: PayloadAction<number>) {
      const segmentIndex = action.payload;
      if (state.segments[segmentIndex]) {
        state.segments[segmentIndex].isComplete = true;
        
        const nextIndex = segmentIndex + 1;
        if (nextIndex < state.segments.length) {
          state.currentTypingIndex = nextIndex;
          state.isTyping = true;
        } else {
          state.currentTypingIndex = -1;
          state.isTyping = false;
        }
      }
    },

    setFinalTranscript(state, action: PayloadAction<FinalEvent>) {
      const { teacher_speaker, speaker_text_stats } = action.payload
      state.teacherSpeaker = teacher_speaker
      state.speakerStats = speaker_text_stats

      if (teacher_speaker) {
        for (const seg of state.segments) {
          if (seg.speaker === teacher_speaker) seg.speaker = 'TEACHER'
        }
      }
    },

    finishTranscript(state) {
      state.status = 'done'
      state.isTyping = false
      state.segments.forEach(seg => seg.isComplete = true);
      state.currentTypingIndex = -1;
      state.shouldSwitchToSummary = true;
    },

    resetSwitchToSummary(state) {
      state.shouldSwitchToSummary = false;
    }
  }
})

export const {
  resetTranscript,
  startTranscript,
  appendTranscriptChunk,
  completeSegmentTyping,
  setFinalTranscript,
  finishTranscript,
  resetSwitchToSummary
} = transcriptSlice.actions

export default transcriptSlice.reducer