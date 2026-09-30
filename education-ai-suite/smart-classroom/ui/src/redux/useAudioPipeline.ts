import { useEffect, useRef } from 'react';
import { useAppDispatch, useAppSelector } from './hooks';
import {
  appendTranscriptChunk,
  setFinalTranscript,
  finishTranscript,
  setTotalDuration,
  updateSpeakerStats,
} from './slices/transcriptSlice';
import {
  startTranscription,
  transcriptionComplete,
  clearSummaryStartRequest,
  firstSummaryToken,
  summaryStreamComplete,
  summaryDone,
  clearMindmapStartRequest,
  mindmapLoadingStart,
  mindmapSuccess,
  mindmapFailed,
} from './slices/uiSlice';
import {
  startSummary,
  appendSummary,
  finishSummary,
  setSummaryProgress,
  setBoardOcrPartial,
} from './slices/summarySlice';
import {
  startMindmap,
  setMindmap,
  setError as setMindmapError,
} from './slices/mindmapSlice';
import { streamTranscript, streamSummary, fetchMindmap } from '../services/api';
import { useFeatureConfig } from '../hooks/useFeatureConfig';

// Guards against a second run for the same session surviving a remount of the
// hook (React StrictMode mounts effects twice in development).
const activeTranscriptSessions = new Set<string>();
const activeSummarySessions = new Set<string>();
const activeMindmapSessions = new Set<string>();

/**
 * Drives the audio pipeline — transcript stream, then summary stream, then the
 * mind-map fetch — along with the audioStatus transitions the rest of the UI
 * reads (upload gate, notifications, report auto-generation).
 *
 * This deliberately lives outside the tab components. LeftPanel mounts each tab
 * only while it is the active tab, so while this work ran there, switching tabs
 * mid-run abandoned the stage in flight: the transcript stream returned at its
 * next event and `transcriptionComplete` was skipped outright (it was guarded on
 * the component still being mounted), and the mind-map fetch never started if
 * its tab was never opened. audioStatus then stayed on 'transcribing' /
 * 'mindmapping' for the rest of the session, which stalled every later stage
 * and left both Upload File buttons greyed out (see usePipelineGate).
 *
 * Mounted once from App, the chain always runs to completion; the tabs only
 * render what it produced.
 */
export function useAudioPipeline() {
  useTranscriptStage();
  useSummaryStage();
  useMindmapStage();
}

/** Streams the transcript, then hands off to the summary stage. */
function useTranscriptStage() {
  const dispatch = useAppDispatch();
  const { guard, loaded: featuresLoaded } = useFeatureConfig();
  const hasAsrFeature = featuresLoaded && guard.hasFeature('asr');
  const hasSummaryFeature = featuresLoaded && guard.hasFeature('summary');

  const aiProcessing = useAppSelector((s) => s.ui.aiProcessing);
  const uploadedAudioPath = useAppSelector((s) => s.ui.uploadedAudioPath);
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const transcriptionDone = useAppSelector((s) => s.ui.transcriptionDone);
  const segments = useAppSelector((s) => s.transcript.segments);
  const teacherSpeaker = useAppSelector((s) => s.transcript.teacherSpeaker);

  // Read inside the stream loop, so they must be refs rather than deps: a new
  // value must not restart the stream.
  const segmentsRef = useRef(segments);
  const teacherSpeakerRef = useRef(teacherSpeaker);
  const hasSummaryFeatureRef = useRef(hasSummaryFeature);
  segmentsRef.current = segments;
  teacherSpeakerRef.current = teacherSpeaker;
  hasSummaryFeatureRef.current = hasSummaryFeature;

  const startedRef = useRef(false);
  const transcriptionStartedRef = useRef(false);
  const finishedRef = useRef(false);
  const finishTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    startedRef.current = false;
    transcriptionStartedRef.current = false;
    finishedRef.current = false;
  }, [sessionId]);

  useEffect(
    () => () => {
      if (finishTimeoutRef.current) clearTimeout(finishTimeoutRef.current);
    },
    [],
  );

  useEffect(() => {
    if (!hasAsrFeature) return;
    if (!aiProcessing || !uploadedAudioPath || !sessionId) return;
    if (startedRef.current || transcriptionDone) {
      console.log('🎯 Transcript stream prevented:', {
        aiProcessing,
        uploadedAudioPath: !!uploadedAudioPath,
        started: startedRef.current,
        transcriptionDone,
      });
      return;
    }
    if (activeTranscriptSessions.has(sessionId)) return;

    console.log('🎯 Starting transcript stream for session:', sessionId);
    startedRef.current = true;
    activeTranscriptSessions.add(sessionId);
    finishedRef.current = false;

    // Marks the transcript finished and starts the summary stage. Runs at most
    // once per session, whether the stream ended, errored or failed outright.
    const finalizeTranscript = () => {
      if (finishedRef.current) return;
      finishedRef.current = true;
      dispatch(finishTranscript());

      setTimeout(() => {
        dispatch(transcriptionComplete({ enableSummary: hasSummaryFeatureRef.current }));
      }, 150);
    };

    const run = async () => {
      try {
        const stream = streamTranscript(uploadedAudioPath, sessionId);

        for await (const ev of stream) {
          if (ev.type === 'transcript_chunk') {
            if (!transcriptionStartedRef.current) {
              transcriptionStartedRef.current = true;
              dispatch(startTranscription());
            }

            const chunkData = ev.data;
            if (chunkData.segments && Array.isArray(chunkData.segments)) {
              const processedSegments = chunkData.segments.map((segment: any) => {
                const offset = chunkData.start_time || 0;
                const useOffset = segment.start < offset;

                return {
                  ...segment,
                  start: useOffset ? segment.start + offset : segment.start,
                  end: useOffset ? segment.end + offset : segment.end,
                };
              });

              dispatch(appendTranscriptChunk({
                ...chunkData,
                segments: processedSegments
              }));
            } else {
              dispatch(appendTranscriptChunk(chunkData));
            }
          }

          else if (ev.type === 'transcript' && typeof ev.token === 'string') {
            if (!transcriptionStartedRef.current) {
              transcriptionStartedRef.current = true;
              dispatch(startTranscription());
            }
            dispatch(appendTranscriptChunk({ text: ev.token }));
          }

          else if (ev.type === 'final') {
            console.log('📋 Final transcript data received:', ev.data);
            dispatch(setFinalTranscript(ev.data));

            if (ev.data.teacher_speaker) {
              console.log('👨‍🏫 Teacher speaker identified:', ev.data.teacher_speaker);
            }

            if (ev.data.speaker_text_stats) {
              console.log('📊 Speaker stats received:', ev.data.speaker_text_stats);
              dispatch(updateSpeakerStats(ev.data.speaker_text_stats));
            }
          }

          else if (ev.type === 'error') {
            console.error('❌ Transcription error:', ev.message);
            finalizeTranscript();
            break;
          }

          else if (ev.type === 'done') {
            console.log('📋 Transcript stream done');

            const latestSegments = segmentsRef.current;
            if (latestSegments.length > 0) {
              const maxEnd = Math.max(...latestSegments.map(s => s.end || 0).filter(end => end > 0));
              if (maxEnd > 0) {
                console.log('⏱️ Setting total duration from segments:', maxEnd);
                dispatch(setTotalDuration(maxEnd));
              }

              const speakerStats: { [speaker: string]: number } = {};
              latestSegments.forEach(segment => {
                if (segment.start !== undefined && segment.end !== undefined) {
                  const duration = segment.end - segment.start;
                  speakerStats[segment.speaker] = (speakerStats[segment.speaker] || 0) + duration;
                }
              });

              if (Object.keys(speakerStats).length > 0) {
                dispatch(updateSpeakerStats(speakerStats));
              }
            }

            // Leaves the last segments time to finish typing in TranscriptsTab
            // before the UI moves on to the summary tab.
            finishTimeoutRef.current = window.setTimeout(
              finalizeTranscript,
              teacherSpeakerRef.current ? 2500 : 3000,
            );

            break;
          }
        }
      } catch (err) {
        console.error('❌ Transcript stream failed:', err);
        finalizeTranscript();
      } finally {
        activeTranscriptSessions.delete(sessionId);
      }
    };

    run();
  }, [hasAsrFeature, aiProcessing, uploadedAudioPath, sessionId, transcriptionDone, dispatch]);
}

/** Streams the summary, then hands off to the mind-map stage. */
function useSummaryStage() {
  const dispatch = useAppDispatch();
  const { guard, loaded: featuresLoaded } = useFeatureConfig();
  const hasMindmapFeature = featuresLoaded && guard.hasFeature('mindmap');

  const summaryEnabled = useAppSelector((s) => s.ui.summaryEnabled);
  const shouldStartSummary = useAppSelector((s) => s.ui.shouldStartSummary);
  const sessionId = useAppSelector((s) => s.ui.sessionId);

  const hasMindmapFeatureRef = useRef(hasMindmapFeature);
  hasMindmapFeatureRef.current = hasMindmapFeature;

  const startedRef = useRef(false);
  const sessionRef = useRef<string | null>(null);

  useEffect(() => {
    if (sessionRef.current && sessionRef.current !== sessionId) {
      activeSummarySessions.delete(sessionRef.current);
      startedRef.current = false;
    }
    sessionRef.current = sessionId ?? null;
  }, [sessionId]);

  useEffect(() => {
    if (!summaryEnabled || !sessionId || !shouldStartSummary) return;
    if (activeSummarySessions.has(sessionId) || startedRef.current) return;

    startedRef.current = true;
    activeSummarySessions.add(sessionId);
    dispatch(clearSummaryStartRequest());
    dispatch(startSummary());

    // Every exit path reports the summary as done: the mind map and everything
    // gated on audioStatus behind it must not wait on a stream that stopped.
    const finish = () => {
      dispatch(finishSummary());
      dispatch(summaryStreamComplete());
      dispatch(summaryDone({ enableMindmap: hasMindmapFeatureRef.current }));
    };

    (async () => {
      try {
        let sentFirst = false;
        for await (const ev of streamSummary(sessionId)) {
          if (ev.type === 'summary_token') {
            if (!sentFirst) {
              dispatch(firstSummaryToken());
              sentFirst = true;
            }
            dispatch(appendSummary(ev.token));
          } else if (ev.type === 'board_ocr_partial') {
            dispatch(setBoardOcrPartial(true));
          } else if (ev.type === 'summary_progress') {
            dispatch(setSummaryProgress({ stage: ev.stage, chunk: ev.chunk, chunks: ev.chunks }));
          } else if (ev.type === 'error') {
            window.dispatchEvent(new CustomEvent('global-error', { detail: ev.message || 'Summary error' }));
            finish();
            break;
          } else if (ev.type === 'done') {
            finish();
            break;
          }
        }
      } catch (e: any) {
        if (e?.name !== 'AbortError') console.error('[useAudioPipeline] summary stream error', e);
        finish();
      } finally {
        console.log('[useAudioPipeline] summary stream finished', sessionId);
      }
    })();
  }, [summaryEnabled, shouldStartSummary, sessionId, dispatch]);
}

/**
 * Fetches the mind map. Rendering it (and the report screenshot taken from the
 * rendered view) stays in MindMapTab, which needs the DOM for both.
 */
function useMindmapStage() {
  const dispatch = useAppDispatch();

  const mindmapEnabled = useAppSelector((s) => s.ui.mindmapEnabled);
  const shouldStartMindmap = useAppSelector((s) => s.ui.shouldStartMindmap);
  const summaryComplete = useAppSelector((s) => s.ui.summaryComplete);
  const mindmapLoading = useAppSelector((s) => s.ui.mindmapLoading);
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const { finalText, sessionId: mindmapSessionId } = useAppSelector((s) => s.mindmap);

  // Read inside the effect but not listed as deps: they change while the fetch
  // is in flight, and re-running the effect on them is exactly what the guards
  // below exist to prevent.
  const mindmapLoadingRef = useRef(false);
  const finalTextRef = useRef<string | null>(null);
  const mindmapSessionIdRef = useRef<string | null>(null);
  mindmapLoadingRef.current = mindmapLoading;
  finalTextRef.current = finalText ?? null;
  mindmapSessionIdRef.current = mindmapSessionId ?? null;

  const startedRef = useRef(false);
  const sessionRef = useRef<string | null>(null);

  useEffect(() => {
    if (sessionRef.current && sessionRef.current !== sessionId) {
      activeMindmapSessions.delete(sessionRef.current);
      startedRef.current = false;
    }
    sessionRef.current = sessionId ?? null;
  }, [sessionId]);

  useEffect(() => {
    if (!mindmapEnabled || !sessionId || !shouldStartMindmap) return;
    if (!summaryComplete) return;
    // Already have a result for this session (read via refs — not deps)
    if (mindmapSessionIdRef.current === sessionId && finalTextRef.current) return;
    // Redux-level guard: already fetching
    if (mindmapLoadingRef.current) return;
    // Module/hook-level guards
    if (activeMindmapSessions.has(sessionId) || startedRef.current) return;

    startedRef.current = true;
    activeMindmapSessions.add(sessionId);

    dispatch(startMindmap({ sessionId, startedAt: performance.now() }));
    // Show the tab spinner while the request is in flight. Uses the
    // loading-only action: mindmapStart would re-set shouldStartMindmap=true,
    // which causes the effect to re-fire and hit the backend repeatedly.
    dispatch(mindmapLoadingStart());
    // Clear the trigger flag BEFORE the async call to stop re-entry.
    dispatch(clearMindmapStartRequest());

    (async () => {
      try {
        const fullMindmap = await fetchMindmap(sessionId);

        if (typeof fullMindmap === 'string' && fullMindmap.length > 0) {
          dispatch(setMindmap(fullMindmap));
          dispatch(mindmapSuccess());
        } else {
          throw new Error('Empty mindmap returned');
        }
      } catch (err: any) {
        console.error('❌ Mindmap fetch error:', err);
        dispatch(setMindmapError(err.message || 'Mindmap generation failed'));
        dispatch(mindmapFailed());
      } finally {
        dispatch(clearMindmapStartRequest());
      }
    })();
  }, [mindmapEnabled, sessionId, summaryComplete, shouldStartMindmap, dispatch]);
}
