import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export interface TranscriptSegment {
  id: string;
  speaker: string;
  text: string;
  start?: number;
  end?: number;
  isComplete: boolean;
}

type SupportedLanguage = "en" | "zh";

interface TranscriptState {
  segments: TranscriptSegment[];
  currentTypingIndex: number;
  isFinished: boolean;
  teacherSpeaker: string | null;
  totalDuration: number | null;
  speakerStats: { [speaker: string]: number };
  detectedLanguage: SupportedLanguage | null;
}

const initialState: TranscriptState = {
  segments: [],
  currentTypingIndex: -1,
  isFinished: false,
  teacherSpeaker: null,
  totalDuration: null,
  speakerStats: {},
  detectedLanguage: null,
};

const normalizeSpeaker = (s?: string | null) =>
  s?.trim().toUpperCase() || "";

export const transcriptSlice = createSlice({
  name: "transcript",
  initialState,
  reducers: {
    appendTranscriptChunk: (state, action: PayloadAction<any>) => {
      const chunk = action.payload;

      if (chunk.segments && Array.isArray(chunk.segments)) {
        chunk.segments.forEach((segment: any) => {
          const speaker = normalizeSpeaker(segment.speaker);

          const newSegment: TranscriptSegment = {
            id: `${speaker}-${Date.now()}-${Math.random()}`,
            speaker,
            text: segment.text,
            start: segment.start ?? 0,
            end: segment.end ?? 0,
            isComplete: false,
          };

          state.segments.push(newSegment);
        });

        if (state.segments.length > 0 && state.currentTypingIndex < 0) {
          state.currentTypingIndex = 0;
        }

        if (chunk.end_time) {
          state.totalDuration = Math.max(
            state.totalDuration || 0,
            chunk.end_time
          );
        }
      }

      else if (chunk.text) {
        const speaker = normalizeSpeaker(
          chunk.speaker || state.segments[state.segments.length - 1]?.speaker || "SPEAKER_00"
        );

        if (state.segments.length === 0) {
          const newSegment: TranscriptSegment = {
            id: `segment-${Date.now()}`,
            speaker,
            text: chunk.text,
            start: chunk.start,
            end: chunk.end,
            isComplete: false,
          };
          state.segments.push(newSegment);
          state.currentTypingIndex = 0;
        } else {
          const lastSegment = state.segments[state.segments.length - 1];

          if (
            normalizeSpeaker(lastSegment.speaker) === speaker &&
            !lastSegment.isComplete
          ) {
            lastSegment.text += chunk.text;
            if (chunk.end) lastSegment.end = chunk.end;
          } else {
            const newSegment: TranscriptSegment = {
              id: `segment-${Date.now()}-${Math.random()}`,
              speaker,
              text: chunk.text,
              start: chunk.start,
              end: chunk.end,
              isComplete: false,
            };
            state.segments.push(newSegment);
          }
        }
      }
    },

    setFinalTranscript: (state, action: PayloadAction<any>) => {
      const finalData = action.payload;

      if (finalData.teacher_speaker) {
        state.teacherSpeaker = normalizeSpeaker(
          finalData.teacher_speaker
        );
      }

      if (finalData.speaker_text_stats) {
        const normalizedStats: { [speaker: string]: number } = {};
        Object.entries(finalData.speaker_text_stats).forEach(
          ([speaker, value]) => {
            normalizedStats[normalizeSpeaker(speaker)] = value as number;
          }
        );
        state.speakerStats = normalizedStats;
      }

      if (state.segments.length > 0) {
        const maxEnd = Math.max(
          ...state.segments
            .map(s => s.end || 0)
            .filter(e => e > 0)
        );

        if (maxEnd > 0) {
          state.totalDuration = Math.max(
            state.totalDuration || 0,
            maxEnd
          );
        }
      }


      state.segments.forEach(segment => {
        segment.isComplete = true;
      });
    },

    finishTranscript: (state) => {
      state.isFinished = true;
      state.currentTypingIndex = -1;
      state.segments.forEach(segment => {
        segment.isComplete = true;
      });
    },

    completeSegmentTyping: (state, action: PayloadAction<number>) => {
      const idx = action.payload;
      if (idx >= 0 && idx < state.segments.length) {
        state.segments[idx].isComplete = true;
        const next = idx + 1;
        state.currentTypingIndex =
          next < state.segments.length ? next : -1;
      }
    },

    setTotalDuration: (state, action: PayloadAction<number>) => {
      state.totalDuration = Math.max(
        state.totalDuration || 0,
        action.payload
      );
    },

    updateSpeakerStats: (
      state,
      action: PayloadAction<{ [speaker: string]: number }>
    ) => {
      const normalizedStats: { [speaker: string]: number } = {};
      Object.entries(action.payload).forEach(([speaker, value]) => {
        normalizedStats[normalizeSpeaker(speaker)] = value;
      });
      state.speakerStats = normalizedStats;
    },

    setDetectedLanguage: (
      state,
      action: PayloadAction<SupportedLanguage>
    ) => {
      state.detectedLanguage = action.payload;
    },

    resetTranscript: (state) => {
      state.segments = [];
      state.currentTypingIndex = -1;
      state.isFinished = false;
      state.teacherSpeaker = null;
      state.totalDuration = null;
      state.speakerStats = {};
      state.detectedLanguage = null;
    },
  },
});

export const {
  appendTranscriptChunk,
  setFinalTranscript,
  finishTranscript,
  completeSegmentTyping,
  setTotalDuration,
  updateSpeakerStats,
  setDetectedLanguage,
  resetTranscript,
} = transcriptSlice.actions;

export default transcriptSlice.reducer;
