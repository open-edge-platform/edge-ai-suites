import { useCallback, useRef, useState } from "react";
import { AUDIO, POLL_INTERVAL_MS } from "../config";
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
  const [status, setStatus] = useState("Idle — tap the mic to ask a question.");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [partialUser, setPartialUser] = useState("");
  const [partialAssistant, setPartialAssistant] = useState("");
  const [micAnalyser, setMicAnalyser] = useState<AnalyserNode | null>(null);
  const [responseAnalyser, setResponseAnalyser] = useState<AnalyserNode | null>(null);
  const [responseActive, setResponseActive] = useState(false);
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
    async (wav: ArrayBuffer) => {
      pendingChunks.current.push(wav);
      if (!sessionIdRef.current && !startingRef.current) {
        startingRef.current = true;
        try {
          const history = messagesRef.current.map((m) => ({
            role: m.role,
            content: m.text,
          }));
          const snap = await startStreamSession(AUDIO.sampleRate, history, {
            chunkSeconds: AUDIO.sessionChunkSeconds,
            silenceTimeoutSeconds: AUDIO.silenceTimeoutSeconds,
            maxSessionSeconds: AUDIO.maxSessionSeconds,
            silenceThreshold: AUDIO.silenceThreshold,
          });
          sessionIdRef.current = snap.session_id;
        } catch (err) {
          setStatus(`❌ ${err instanceof Error ? err.message : "Could not start session"}`);
        } finally {
          startingRef.current = false;
        }
      }
      await flushPending();
    },
    [flushPending]
  );

  const start = useCallback(async (deviceId?: string) => {
    setPartialUser("");
    setPartialAssistant("");
    sessionIdRef.current = null;
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
    setStatus("⏳ Processing…");
    const recorder = recorderRef.current;
    recorderRef.current = null;
    if (recorder) await recorder.stop();
    setMicAnalyser(null);
    await flushPending();

    const sid = sessionIdRef.current;
    if (!sid) {
      setStatus("No audio captured — try again.");
      return;
    }

    try {
      await endAudioStream(sid);
    } catch (err) {
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

  return {
    recording,
    status,
    messages,
    partialUser,
    partialAssistant,
    micAnalyser,
    responseAnalyser,
    responseActive,
    sessionPerf,
    sessionPerfSeries,
    start,
    stop,
  };
}
