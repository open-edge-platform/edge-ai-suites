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

type TranscriptStatus = "idle" | "streaming" | "finalizing" | "complete" | "error";

interface TranscriptState {
  segments: TranscriptSegment[];
  currentTypingIndex: number;
  isFinished: boolean;
  teacherSpeaker: string | null;
  totalDuration: number | null;
  speakerStats: { [speaker: string]: number };
  detectedLanguage: SupportedLanguage | null;
  status: TranscriptStatus;
}

const initialState: TranscriptState = {
  segments: [],
  currentTypingIndex: -1,
  isFinished: false,
  teacherSpeaker: null,
  totalDuration: null,
  speakerStats: {},
  detectedLanguage: null,
  status: "idle",
};

const normalizeSpeaker = (s?: string | null) => s?.trim().toUpperCase() || "";


const shouldMerge = (last?: TranscriptSegment, incoming?: { speaker?: string; start?: number; end?: number }) => {
  if (!last || !incoming) return false;
  const inSpeaker = normalizeSpeaker(incoming.speaker);
  if (normalizeSpeaker(last.speaker) !== inSpeaker) return false;

  const lastEnd = last.end ?? 0;
  const inStart = incoming.start ?? lastEnd;

  return inStart - lastEnd <= 0.8;
};

const makeStableId = (speaker: string, start?: number, fallbackIndex?: number) => {
  const s = normalizeSpeaker(speaker);
  const t = Math.round((start ?? 0) * 1000);
  if (t > 0) return `${s}:${t}`;
  return `${s}:idx:${fallbackIndex ?? 0}`;
};

export const transcriptSlice = createSlice({
  name: "transcript",
  initialState,
  reducers: {
    appendTranscriptChunk: (state, action: PayloadAction<any>) => {
      const chunk = action.payload;

      if (chunk.segments && Array.isArray(chunk.segments)) {
        for (const seg of chunk.segments) {
          const speaker = normalizeSpeaker(seg.speaker);
          const start = seg.start ?? 0;
          const end = seg.end ?? start;
          const last = state.segments[state.segments.length - 1];

          if (shouldMerge(last, { speaker, start, end })) {
            if (seg.text && seg.text.trim().length > 0) {
              last.text = (last.text + " " + seg.text).replace(/\s+/g, " ").trim();
            }
            last.end = Math.max(last.end ?? 0, end);
            last.isComplete = false;
            state.currentTypingIndex = state.segments.length - 1;
          } else {
            if (last && !last.isComplete) {
              last.isComplete = true;
            }

            const newSeg: TranscriptSegment = {
              id: makeStableId(speaker, start, state.segments.length),
              speaker,
              text: (seg.text ?? "").trim(),
              start,
              end,
              isComplete: false,
            };
            state.segments.push(newSeg);
            state.currentTypingIndex = state.segments.length - 1;
          }
        }

        if (chunk.end_time) {
          state.totalDuration = Math.max(state.totalDuration || 0, chunk.end_time);
        }
      }

      else if (chunk.text) {
        const text = String(chunk.text ?? "");
        const speaker = normalizeSpeaker(
          chunk.speaker || state.segments[state.segments.length - 1]?.speaker || "SPEAKER_00"
        );

        if (state.segments.length === 0) {
          const newSegment: TranscriptSegment = {
            id: makeStableId(speaker, chunk.start, 0),
            speaker,
            text,
            start: chunk.start,
            end: chunk.end ?? chunk.start,
            isComplete: false,
          };
          state.segments.push(newSegment);
          state.currentTypingIndex = 0;
        } else {
          const last = state.segments[state.segments.length - 1];
          if (normalizeSpeaker(last.speaker) === speaker && !last.isComplete) {
            last.text = (last.text + text).replace(/\s+/g, " ").trim();
            if (chunk.end) last.end = Math.max(last.end ?? 0, chunk.end);
            state.currentTypingIndex = state.segments.length - 1;
          } else {
            if (!last.isComplete) last.isComplete = true;
            const newSegment: TranscriptSegment = {
              id: makeStableId(speaker, chunk.start, state.segments.length),
              speaker,
              text,
              start: chunk.start,
              end: chunk.end ?? chunk.start,
              isComplete: false,
            };
            state.segments.push(newSegment);
            state.currentTypingIndex = state.segments.length - 1;
          }
        }
      }
    },

    setFinalTranscript: (state, action: PayloadAction<any>) => {
      const finalData = action.payload;

      if (finalData.teacher_speaker) {
        state.teacherSpeaker = normalizeSpeaker(finalData.teacher_speaker);
      }

      if (finalData.speaker_text_stats) {
        const normalizedStats: { [speaker: string]: number } = {};
        Object.entries(finalData.speaker_text_stats).forEach(([speaker, value]) => {
          normalizedStats[normalizeSpeaker(speaker)] = value as number;
        });
        state.speakerStats = normalizedStats;
      }

      if (state.segments.length > 0) {
        const maxEnd = Math.max(
          ...state.segments.map(s => s.end || 0).filter(e => e > 0)
        );
        if (maxEnd > 0) {
          state.totalDuration = Math.max(state.totalDuration || 0, maxEnd);
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
        state.currentTypingIndex = next < state.segments.length ? next : -1;
      }
    },

    setTotalDuration: (state, action: PayloadAction<number>) => {
      state.totalDuration = Math.max(state.totalDuration || 0, action.payload);
    },

    updateSpeakerStats: (state, action: PayloadAction<{ [speaker: string]: number }>) => {
      const normalizedStats: { [speaker: string]: number } = {};
      Object.entries(action.payload).forEach(([speaker, value]) => {
        normalizedStats[normalizeSpeaker(speaker)] = value;
      });
      state.speakerStats = normalizedStats;
    },

    setDetectedLanguage: (state, action: PayloadAction<SupportedLanguage>) => {
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