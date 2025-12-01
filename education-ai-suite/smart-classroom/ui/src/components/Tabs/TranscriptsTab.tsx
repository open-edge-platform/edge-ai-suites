import React, { useEffect, useRef } from "react";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import { appendTranscript, finishTranscript, startTranscript } from "../../redux/slices/transcriptSlice";
import { transcriptionComplete, setSessionId } from "../../redux/slices/uiSlice";
import { streamTranscript, createSession } from "../../services/api";

const TranscriptsTab: React.FC = () => {
  const dispatch = useAppDispatch();
  const abortRef = useRef<AbortController | null>(null);
  const startedRef = useRef(false);
  const { finalText, streamingText } = useAppSelector(s => s.transcript);
  const aiProcessing = useAppSelector(s => s.ui.aiProcessing);
  const audioPath = useAppSelector(s => s.ui.uploadedAudioPath); 
  const sessionId = useAppSelector(s => s.ui.sessionId); 

  useEffect(() => {
    console.log('Updated sessionId:', sessionId);
  }, [sessionId]);

  useEffect(() => {
    console.log('TranscriptsTab useEffect:', { aiProcessing, audioPath, sessionId, startedRef: startedRef.current });
    if (!aiProcessing || !audioPath || startedRef.current || audioPath.includes('storage\\')) {
      return;
    }
    console.log('🎤 TranscriptsTab: Starting transcript stream');
    startedRef.current = true;

    const aborter = new AbortController();
    abortRef.current = aborter;

    const run = async () => {
      try {
        let currentSessionId = sessionId;
        if (!currentSessionId) {
          console.log('🆔 TranscriptsTab: No session ID found, creating new session');
          const sessionResponse = await createSession();
          currentSessionId = sessionResponse.sessionId;
          console.log('✅ TranscriptsTab: Session created:', currentSessionId);
          dispatch(setSessionId(currentSessionId));
        }

        console.log('🎯 TranscriptsTab: Starting stream with session ID:', currentSessionId);
        
        const stream = streamTranscript(audioPath, currentSessionId, {
          signal: aborter.signal,
          tokenDelayMs: 120,
          onSessionId: (id) => {
            console.log('🆔 TranscriptsTab: Confirmed sessionId:', id);
          }, 
        });

        let sentFirst = false;
        
        for await (const ev of stream) {
          if (ev.type === "transcript") {
            if (!sentFirst) { 
              dispatch(startTranscript()); 
              sentFirst = true; 
            }
            dispatch(appendTranscript(ev.token));
          } else if (ev.type === 'error') {
            console.error('❌ TranscriptsTab: Transcription error:', ev.message);
            window.dispatchEvent(new CustomEvent('global-error', { detail: ev.message || 'Transcription error' }));
            dispatch(finishTranscript());
            break;
          } else if (ev.type === 'done') {
            console.log('✅ TranscriptsTab: Transcription completed');
            dispatch(finishTranscript());
            dispatch(transcriptionComplete());
            break;
          }
        }
      } catch (error) {
        const isAbortError = error instanceof Error && error.name === 'AbortError';
        if (!isAbortError) {
          console.error('❌ TranscriptsTab: Stream error:', error);
        }
      }
    };

    run();
    return () => {
      console.log('🛑 TranscriptsTab: Cleaning up, aborting stream');
      aborter.abort();
    };
  }, [dispatch, aiProcessing, audioPath, sessionId]); 

  const text = finalText ?? streamingText;

  return (
    <div className="transcripts-tab">
      <div className="transcript-content">
        {text && text.trim().length > 0
          ? text
          : <span style={{ color: "#888" }}></span>
        }
      </div>
    </div>
  );
};

export default TranscriptsTab;