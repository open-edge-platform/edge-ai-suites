import React, { useEffect, useRef } from "react";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import { appendTranscript, finishTranscript, startTranscript } from "../../redux/slices/transcriptSlice";
import { transcriptionComplete, setSessionId } from "../../redux/slices/uiSlice";
import { streamTranscript } from "../../services/api";

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

// In TranscriptsTab.tsx
useEffect(() => {
  console.log('TranscriptsTab useEffect:', { aiProcessing, audioPath, startedRef: startedRef.current });
  
  // Don't start if there's an uploaded audio path (means UploadFilesModal is handling it)
  if (!aiProcessing || !audioPath || startedRef.current || audioPath.includes('storage\\')) {
    console.log('🚫 TranscriptsTab: Skipping - uploaded file detected or other condition');
    return;
  }
  
  console.log('🎤 TranscriptsTab: Starting transcript stream');
  startedRef.current = true;

  const aborter = new AbortController();
  abortRef.current = aborter;

  const run = async () => {
    const stream = streamTranscript(audioPath, {
      signal: aborter.signal,
      tokenDelayMs: 120,
      onSessionId: (id) => {
        console.log('Dispatching setSessionId:', id);
        dispatch(setSessionId(id));
      }, 
    });
    let sentFirst = false;
    try {
      for await (const ev of stream) {
        if (ev.type === "transcript") {
          if (!sentFirst) { dispatch(startTranscript()); sentFirst = true; }
          dispatch(appendTranscript(ev.token));
        } else if (ev.type === 'error') {
          window.dispatchEvent(new CustomEvent('global-error', { detail: ev.message || 'Transcription error' }));
          dispatch(finishTranscript());
          break;
        } else if (ev.type === 'done') {
          dispatch(finishTranscript());
          dispatch(transcriptionComplete());
          break;
        }
      }
    } catch { /* ignore aborts */ }
  };

  run();
  return () => aborter.abort();
}, [dispatch, aiProcessing, audioPath]);

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