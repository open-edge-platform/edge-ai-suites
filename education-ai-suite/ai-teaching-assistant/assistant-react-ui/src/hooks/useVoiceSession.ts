import { useCallback, useEffect, useRef, useState } from "react";
import { AUDIO, INACTIVITY_RESET_MS, POLL_INTERVAL_MS } from "../config";
import {
  endAudioStream,
  getSession,
  pushAudioChunk,
  responseAudioUrl,
  startStreamSession,
} from "../api";
import { MicRecorder } from "../audio/MicRecorder";
import { ResponsePlayer } from "../audio/ResponsePlayer";
import type { ChatMessage, SessionPerfSnapshot } from "../types";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const MAX_SESSION_POINTS = 90;

function keepLast(values: number[], next: number): number[] {
  const updated = [...values, next];
  return updated.length > MAX_SESSION_POINTS
    ? updated.slice(updated.length - MAX_SESSION_POINTS)
    : updated;
}

export function useVoiceSession() {
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [status, setStatus] = useState("Idle — tap the mic to ask a question.");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [partialUser, setPartialUser] = useState("");
  const [partialAssistant, setPartialAssistant] = useState("");
  const [micAnalyser, setMicAnalyser] = useState<AnalyserNode | null>(null);
  const [responseAnalyser, setResponseAnalyser] = useState<AnalyserNode | null>(null);
  const [responseActive, setResponseActive] = useState(false);
  const [resetIn, setResetIn] = useState<number | null>(null);
  const [sessionPerf, setSessionPerf] = useState<SessionPerfSnapshot>({
    ttstMs: null,
    endToEndMs: null,
    rtf: null,
  });
  const [sessionPerfSeries, setSessionPerfSeries] = useState({
    ttstMs: [] as number[],
    endToEndMs: [] as number[],
    rtf: [] as number[],
  });

  const recorderRef = useRef<MicRecorder | null>(null);
  const playerRef = useRef<ResponsePlayer | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const startingRef = useRef(false);
  const startPromiseRef = useRef<Promise<void> | null>(null);
  const sessionStartErrorRef = useRef<string | null>(null);
  const streamSampleRateRef = useRef<number>(AUDIO.sampleRate);
  const pendingChunks = useRef<ArrayBuffer[]>([]);
  const messagesRef = useRef<ChatMessage[]>([]);
  messagesRef.current = messages;

  const ensurePlayer = useCallback(() => {
    if (!playerRef.current) {
      const player = new ResponsePlayer();
      player.onStart = () => setResponseActive(true);
      player.onIdle = () => setResponseActive(false);
      playerRef.current = player;
      setResponseAnalyser(player.analyser);
    }
    return playerRef.current;
  }, []);

  const flushPending = useCallback(async () => {
    const sid = sessionIdRef.current;
    if (!sid) return;
    while (pendingChunks.current.length > 0) {
      const chunk = pendingChunks.current.shift()!;
      try {
        await pushAudioChunk(sid, chunk);
      } catch (err) {
        console.warn("chunk push failed", err);
      }
    }
  }, []);

  const onChunk = useCallback(
    async (wav: ArrayBuffer, sampleRate: number) => {
      streamSampleRateRef.current = sampleRate;
      pendingChunks.current.push(wav);
      if (!sessionIdRef.current && !startingRef.current) {
        startingRef.current = true;
        // Track the in-flight start so stop() can await it before deciding
        // whether any audio was captured.
        startPromiseRef.current = (async () => {
          try {
            const history = messagesRef.current.map((m) => ({
              role: m.role,
              content: m.text,
            }));
            const snap = await startStreamSession(streamSampleRateRef.current, history, {
              chunkSeconds: AUDIO.sessionChunkSeconds,
              silenceTimeoutSeconds: AUDIO.silenceTimeoutSeconds,
              maxSessionSeconds: AUDIO.maxSessionSeconds,
              silenceThreshold: AUDIO.silenceThreshold,
            });
            sessionIdRef.current = snap.session_id;
            sessionStartErrorRef.current = null;
          } catch (err) {
            const message = err instanceof Error ? err.message : "Could not start session";
            sessionStartErrorRef.current = message;
            setStatus(`❌ ${message}`);
          } finally {
            startingRef.current = false;
          }
        })();
      }
      if (startPromiseRef.current) await startPromiseRef.current;
      await flushPending();
    },
    [flushPending]
  );

  const start = useCallback(async (deviceId?: string) => {
    setPartialUser("");
    setPartialAssistant("");
    sessionIdRef.current = null;
    startPromiseRef.current = null;
    sessionStartErrorRef.current = null;
    streamSampleRateRef.current = AUDIO.sampleRate;
    pendingChunks.current = [];
    ensurePlayer();
    const recorder = new MicRecorder(AUDIO.sampleRate, AUDIO.chunkSeconds, onChunk);
    try {
      await recorder.start(deviceId);
      recorderRef.current = recorder;
      setMicAnalyser(recorder.analyser);
      setRecording(true);
      setStatus("🎙 Listening — speak now.");
    } catch (err) {
      setStatus(`❌ ${err instanceof Error ? err.message : "Microphone error"}`);
    }
  }, [ensurePlayer, onChunk]);

  const stop = useCallback(async () => {
    const stopStartedAt = performance.now();
    let ttstMs: number | null = null;
    setSessionPerf({ ttstMs: null, endToEndMs: null, rtf: null });
    setRecording(false);
    setProcessing(true);
    setStatus("⏳ Processing…");
    const recorder = recorderRef.current;
    recorderRef.current = null;
    if (recorder) await recorder.stop();
    setMicAnalyser(null);
    // The trailing flush above may have just kicked off session creation; wait
    // for it before deciding whether audio was captured.
    if (startPromiseRef.current) await startPromiseRef.current;
    await flushPending();

    const sid = sessionIdRef.current;
    if (!sid) {
      setProcessing(false);
      if (sessionStartErrorRef.current) {
        setStatus(`❌ ${sessionStartErrorRef.current}`);
      } else {
        setStatus("No audio captured — speak a bit longer and try again.");
      }
      return;
    }

    try {
      await endAudioStream(sid);
    } catch (err) {
      setProcessing(false);
      setStatus(`❌ ${err instanceof Error ? err.message : "End stream failed"}`);
      return;
    }

    const player = ensurePlayer();
    let seenSegments = 0;

    while (true) {
      let snap;
      try {
        snap = await getSession(sid);
      } catch (err) {
        setProcessing(false);
        setStatus(`❌ ${err instanceof Error ? err.message : "Polling failed"}`);
        return;
      }

      const transcript = (snap.transcript ?? "").trim();
      const response = (snap.response ?? "").trim();
      const segments = snap.tts_audio_segments ?? [];
      const running = snap.status === "running" || snap.status === "stopping";

      setPartialUser(transcript);
      setPartialAssistant(response);

      if (segments.length > seenSegments) {
        if (ttstMs === null) {
          ttstMs = Math.max(0, Math.round(performance.now() - stopStartedAt));
          setSessionPerf((prev) => ({ ...prev, ttstMs }));
          setSessionPerfSeries((prev) => ({ ...prev, ttstMs: keepLast(prev.ttstMs, ttstMs!) }));
        }
        for (let i = seenSegments; i < segments.length; i++) {
          player.enqueue(responseAudioUrl(sid, segments[i].index));
        }
        seenSegments = segments.length;
      }

      if (segments.length > 0) setStatus(`🔊 Speaking… (${seenSegments})`);
      else if (response) setStatus("💬 Generating response…");
      else if (transcript) setStatus("📝 Searching the knowledge base…");
      else setStatus("⏳ Processing speech…");

      if (!running) {
        const endToEndMs = Math.max(0, Math.round(performance.now() - stopStartedAt));
        const capturedMs = Math.max(0, (snap.captured_audio_seconds ?? 0) * 1000);
        const rtf = capturedMs > 0 ? Number((endToEndMs / capturedMs).toFixed(3)) : null;

        setSessionPerf({ ttstMs, endToEndMs, rtf });
        setSessionPerfSeries((prev) => ({
          ttstMs: ttstMs !== null ? keepLast(prev.ttstMs, ttstMs) : prev.ttstMs,
          endToEndMs: keepLast(prev.endToEndMs, endToEndMs),
          rtf: rtf !== null ? keepLast(prev.rtf, rtf) : prev.rtf,
        }));

        const committed: ChatMessage[] = [...messagesRef.current];
        if (transcript) committed.push({ role: "user", text: transcript });
        if (response) committed.push({ role: "assistant", text: response });
        setMessages(committed);
        setPartialUser("");
        setPartialAssistant("");
        sessionIdRef.current = null;
        setProcessing(false);
        setStatus(
          snap.tts_errors && snap.tts_errors.length > 0
            ? `⚠ Answered, but speech failed: ${snap.tts_errors.join("; ")}`
            : "✓ Done — tap the mic for another question."
        );
        break;
      }

      await sleep(POLL_INTERVAL_MS);
    }
  }, [ensurePlayer, flushPending]);

  // Instantly clears the current conversation so the next question starts a
  // brand-new session. Because conversation history lives client-side and is
  // forwarded to kiosk-core on each turn, clearing it here resets the session
  // immediately (the backend drops its draft cart when history is empty). No
  // effect while a turn is recording/processing.
  const reset = useCallback(() => {
    if (recording) return;
    playerRef.current?.stop();
    setResponseActive(false);
    pendingChunks.current = [];
    sessionIdRef.current = null;
    startPromiseRef.current = null;
    sessionStartErrorRef.current = null;
    setProcessing(false);
    setMessages([]);
    setPartialUser("");
    setPartialAssistant("");
    setSessionPerf({ ttstMs: null, endToEndMs: null, rtf: null });
    setStatus("Idle — tap the mic to ask a question.");
  }, [recording]);

  // Auto-reset the conversation after a period of inactivity. The countdown
  // only runs when the kiosk is truly idle: there is existing conversation
  // history, the mic is not recording, no turn is being processed, and the
  // assistant is not speaking. Any of those becoming active clears the pending
  // timer, so the 15s window effectively starts once the assistant finishes.
  // `resetIn` exposes the remaining whole seconds for the UI countdown.
  useEffect(() => {
    const idle =
      messages.length > 0 && !recording && !processing && !responseActive;
    if (!idle) {
      setResetIn(null);
      return;
    }
    const deadline = Date.now() + INACTIVITY_RESET_MS;
    setResetIn(Math.ceil(INACTIVITY_RESET_MS / 1000));
    const tick = window.setInterval(() => {
      const remainingMs = deadline - Date.now();
      if (remainingMs <= 0) {
        window.clearInterval(tick);
        reset();
      } else {
        setResetIn(Math.ceil(remainingMs / 1000));
      }
    }, 250);
    return () => {
      window.clearInterval(tick);
      setResetIn(null);
    };
  }, [messages, recording, processing, responseActive, reset]);

  return {
    recording,
    status,
    messages,
    partialUser,
    partialAssistant,
    micAnalyser,
    responseAnalyser,
    responseActive,
    resetIn,
    sessionPerf,
    sessionPerfSeries,
    start,
    stop,
    reset,
  };
}
