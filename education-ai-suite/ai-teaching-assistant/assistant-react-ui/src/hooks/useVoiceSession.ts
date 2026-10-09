import { useCallback, useEffect, useRef, useState } from "react";
import { AUDIO, INACTIVITY_RESET_MS, POLL_INTERVAL_MS, WAKEWORD } from "../config";
import {
  endAudioStream,
  getCaptureMode,
  getSession,
  pushBrowserWakewordAudio,
  pushAudioChunk,
  responseAudioUrl,
  startBrowserWakewordSession,
  startHostSession,
  startStreamSession,
  startTextQuery,
  stopBrowserWakewordSession,
} from "../api";
import { MicRecorder } from "../audio/MicRecorder";
import { ResponsePlayer } from "../audio/ResponsePlayer";
import type { ChatMessage, SessionPerfSnapshot } from "../types";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const MAX_SESSION_POINTS = 90;

type CaptureMode = "host" | "browser";

function keepLast(values: number[], next: number): number[] {
  const updated = [...values, next];
  return updated.length > MAX_SESSION_POINTS
    ? updated.slice(updated.length - MAX_SESSION_POINTS)
    : updated;
}

export function useVoiceSession(deviceId?: string) {
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
  const [wakewordEnabled, setWakewordEnabled] = useState<boolean>(WAKEWORD.enabledByDefault);
  const [wakewordListening, setWakewordListening] = useState(false);
  const [wakewordScore, setWakewordScore] = useState(0);
  // Preferred audio capture source. Resolved once on mount from kiosk-core:
  // "host" when HOST_MIC is enabled on the backend, otherwise "browser".
  // Tracked via captureModeRef; no state needed since only the ref is read.

  const recorderRef = useRef<MicRecorder | null>(null);
  const playerRef = useRef<ResponsePlayer | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const startingRef = useRef(false);
  const startPromiseRef = useRef<Promise<void> | null>(null);
  const sessionStartErrorRef = useRef<string | null>(null);
  const streamSampleRateRef = useRef<number>(AUDIO.sampleRate);
  const pendingChunks = useRef<ArrayBuffer[]>([]);
  const wakewordRecorderRef = useRef<MicRecorder | null>(null);
  const wakewordSessionRef = useRef<string | null>(null);
  const wakewordClosingRef = useRef(false);
  const messagesRef = useRef<ChatMessage[]>([]);
  const wakewordEnabledRef = useRef<boolean>(WAKEWORD.enabledByDefault);
  const wakewordAbortRef = useRef(false);
  const wakewordInFlightRef = useRef(false);
  const wakewordSuppressUntilRef = useRef<number>(0);
  const wakewordCancelVersionRef = useRef(0);
  const autoStopArmedRef = useRef(false);
  const autoStopSilenceMsRef = useRef(0);
  const autoStoppingRef = useRef(false);
  const recordingRef = useRef(false);
  const sendingTextRef = useRef(false);
  const stopRef = useRef<() => Promise<void>>(async () => undefined);
  const captureModeRef = useRef<CaptureMode>("browser");
  // Track the selected device in a ref so wake-word callbacks can read the
  // latest value WITHOUT depending on it. Depending on `deviceId` would
  // recreate runWakewordTurn on every device change, tearing down and
  // restarting the wake-word effect — which could let a stale in-flight turn
  // fall through into start() and auto-record. The ref avoids that restart.
  const deviceIdRef = useRef<string | undefined>(deviceId);
  deviceIdRef.current = deviceId;
  messagesRef.current = messages;

  const setWakewordEnabledSafe = useCallback((enabled: boolean) => {
    wakewordEnabledRef.current = enabled;
    setWakewordEnabled(enabled);
  }, []);

  // Probe kiosk-core once to decide host-mic vs browser-mic capture.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const info = await getCaptureMode();
        const mode: CaptureMode = info.recommended === "host" ? "host" : "browser";
        if (cancelled) return;
        captureModeRef.current = mode;
        setStatus(
          mode === "host"
            ? "Idle — tap the mic to ask a question (host mic)."
            : "Idle — tap the mic to ask a question (browser mic)."
        );
      } catch {
        // Probe failed — keep the safe browser-streaming default.
        captureModeRef.current = "browser";
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

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

  // Polls a kiosk-core session to completion, streaming TTS segments to the
  // player and committing the final transcript/response. Shared by both the
  // browser-stream stop() path and the host-capture turn driver. `startedAt`
  // anchors the latency measurements (time-to-first-speech / end-to-end).
  const pollSessionToCompletion = useCallback(
    async (sid: string, startedAt: number) => {
      const player = ensurePlayer();
      let seenSegments = 0;
      let ttstMs: number | null = null;

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
            ttstMs = Math.max(0, Math.round(performance.now() - startedAt));
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
          const endToEndMs = Math.max(0, Math.round(performance.now() - startedAt));
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
              : "✓ Done"
          );
          // Avoid instantly re-arming wake-word detection on residual room/TTS audio.
          wakewordSuppressUntilRef.current = Date.now() + 1200;
          return;
        }

        await sleep(POLL_INTERVAL_MS);
      }
    },
    [ensurePlayer]
  );

  // Drives a host-captured turn to completion. kiosk-core records from the host
  // mic (with server-side silence detection) and runs RAG+TTS; we just poll and
  // reset the recording flags when it finishes.
  const driveHostTurn = useCallback(
    async (sid: string, startedAt: number) => {
      try {
        await pollSessionToCompletion(sid, startedAt);
      } finally {
        recordingRef.current = false;
        setRecording(false);
        setProcessing(false);
      }
    },
    [pollSessionToCompletion]
  );

  // Host-mic capture: kiosk-core opens the host input device and records the
  // whole turn itself, so the browser never requests microphone access.
  const startHostTurn = useCallback(
    async (deviceId?: string) => {
      setPartialUser("");
      setPartialAssistant("");
      sessionIdRef.current = null;
      sessionStartErrorRef.current = null;
      ensurePlayer();
      const startedAt = performance.now();
      setSessionPerf({ ttstMs: null, endToEndMs: null, rtf: null });
      recordingRef.current = true;
      setRecording(true);
      setProcessing(false);
      setStatus("🎙 Listening — speak now (host mic).");

      let snap;
      try {
        const history = messagesRef.current.map((m) => ({ role: m.role, content: m.text }));
        snap = await startHostSession(AUDIO.sampleRate, history, {
          chunkSeconds: AUDIO.sessionChunkSeconds,
          silenceTimeoutSeconds: AUDIO.silenceTimeoutSeconds,
          maxSessionSeconds: AUDIO.maxSessionSeconds,
          silenceThreshold: AUDIO.silenceThreshold,
          device: deviceId,
        });
      } catch (err) {
        recordingRef.current = false;
        setRecording(false);
        setStatus(`❌ ${err instanceof Error ? err.message : "Could not start host session"}`);
        return;
      }

      sessionIdRef.current = snap.session_id;
      await driveHostTurn(snap.session_id, startedAt);
    },
    [ensurePlayer, driveHostTurn]
  );

  // Sends a typed text query. Skips microphone capture and TTS entirely — the
  // answer is displayed as text only. Reuses the same poll-to-completion path
  // as voice turns (no TTS segments arrive, so nothing is spoken).
  const sendText = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || recordingRef.current || sendingTextRef.current) return;
      sendingTextRef.current = true;
      // Invalidate any in-flight wake-word turn so it cannot also call start().
      wakewordCancelVersionRef.current += 1;
      setProcessing(true);
      setPartialUser(trimmed);
      setPartialAssistant("");
      setStatus("📝 Searching the knowledge base…");
      const startedAt = performance.now();
      setSessionPerf({ ttstMs: null, endToEndMs: null, rtf: null });
      try {
        const history = messagesRef.current.map((m) => ({ role: m.role, content: m.text }));
        const snap = await startTextQuery(trimmed, history);
        sessionIdRef.current = snap.session_id;
        await pollSessionToCompletion(snap.session_id, startedAt);
      } catch (err) {
        setProcessing(false);
        setPartialUser("");
        setStatus(`❌ ${err instanceof Error ? err.message : "Could not send message"}`);
      } finally {
        sendingTextRef.current = false;
      }
    },
    [pollSessionToCompletion]
  );

  const start = useCallback(async (deviceId?: string) => {
    if (captureModeRef.current === "host") {
      await startHostTurn(deviceId);
      return;
    }
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
      recordingRef.current = true;
      setRecording(true);
      setStatus("🎙 Listening — speak now.");
    } catch (err) {
      setStatus(`❌ ${err instanceof Error ? err.message : "Microphone error"}`);
    }
  }, [ensurePlayer, onChunk, startHostTurn]);

  const stop = useCallback(async () => {
    if (!recordingRef.current) {
      return;
    }
    const stopStartedAt = performance.now();
    let ttstMs: number | null = null;
    setSessionPerf({ ttstMs: null, endToEndMs: null, rtf: null });
    recordingRef.current = false;
    setRecording(false);
    autoStopArmedRef.current = false;
    autoStopSilenceMsRef.current = 0;
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
            : "✓ Done"
        );
        // Avoid instantly re-arming wake-word detection on residual room/TTS audio.
        wakewordSuppressUntilRef.current = Date.now() + 1200;
        break;
      }

      await sleep(POLL_INTERVAL_MS);
    }
  }, [ensurePlayer, flushPending]);

  useEffect(() => {
    stopRef.current = stop;
  }, [stop]);

  // Auto-stop recording after 3s silence once speech has started.
  useEffect(() => {
    if (!recording || !micAnalyser) {
      recordingRef.current = false;
      autoStopArmedRef.current = false;
      autoStopSilenceMsRef.current = 0;
      return;
    }

    recordingRef.current = true;

    const intervalMs = 120;
    const data = new Uint8Array(micAnalyser.fftSize);

    const id = window.setInterval(() => {
      if (!recordingRef.current || autoStoppingRef.current) return;

      micAnalyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) {
        const centered = (data[i] - 128) / 128;
        sum += centered * centered;
      }
      const rms = Math.sqrt(sum / data.length);
      const normalized = Math.max(0, Math.min(1, rms * 3.2));

      if (normalized >= AUDIO.autoStopSpeechLevel) {
        autoStopArmedRef.current = true;
        autoStopSilenceMsRef.current = 0;
        return;
      }

      if (!autoStopArmedRef.current) {
        return;
      }

      autoStopSilenceMsRef.current += intervalMs;
      if (autoStopSilenceMsRef.current >= AUDIO.autoStopPauseMs) {
        autoStoppingRef.current = true;
        setStatus("⏸ Silence detected — auto-stopping...");
        void stopRef.current().finally(() => {
          autoStoppingRef.current = false;
          autoStopArmedRef.current = false;
          autoStopSilenceMsRef.current = 0;
        });
      }
    }, intervalMs);

    return () => {
      window.clearInterval(id);
    };
  }, [recording, micAnalyser, stop]);

  const runWakewordTurn = useCallback(async (): Promise<void> => {
    const myVersion = wakewordCancelVersionRef.current;
    setProcessing(false);
    setStatus(`👂 Listening for \"${WAKEWORD.model}\" from browser mic...`);

    let wakewordSessionId: string;
    try {
      const started = await startBrowserWakewordSession({
        sampleRate: AUDIO.sampleRate,
        wakewordModel: WAKEWORD.model,
        wakewordThreshold: WAKEWORD.threshold,
        wakewordVadThreshold: WAKEWORD.vadThreshold,
        wakewordPatienceFrames: WAKEWORD.patienceFrames,
        wakewordInferenceFramework: WAKEWORD.inferenceFramework,
      });
      wakewordSessionId = started.wakeword_session_id;
      wakewordSessionRef.current = wakewordSessionId;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Wake-word activation failed";
      setStatus(`❌ ${msg}`);
      setProcessing(false);
      return;
    }
    let detectedLabel: string | undefined;
    let detectedScore = 0;
    let settled = false;
    let uploadQueue = Promise.resolve();

    const settleOnce = (fn: () => void) => {
      if (settled) return;
      settled = true;
      fn();
    };

    const detectPromise = new Promise<void>((resolve, reject) => {
      const onWakeChunk = (wav: ArrayBuffer) => {
        uploadQueue = uploadQueue
          .then(async () => {
            if (wakewordClosingRef.current || settled) return;
            if (myVersion !== wakewordCancelVersionRef.current) {
              settleOnce(resolve);
              return;
            }
            if (!wakewordEnabledRef.current || wakewordAbortRef.current) {
              settleOnce(resolve);
              return;
            }
            const res = await pushBrowserWakewordAudio(wakewordSessionId, wav);
            setWakewordScore(res.score);
            if (res.detected) {
              detectedLabel = res.detected_label ?? undefined;
              detectedScore = res.score;
              settleOnce(resolve);
            }
          })
          .catch((err) => {
            if (wakewordClosingRef.current || settled) {
              settleOnce(resolve);
              return;
            }
            const msg = err instanceof Error ? err.message : String(err);
            if (msg.includes("Unknown wake-word session")) {
              settleOnce(resolve);
              return;
            }
            settleOnce(() => reject(err));
          });
      };

      const recorder = new MicRecorder(AUDIO.sampleRate, 0.4, async (wav) => {
        onWakeChunk(wav);
      });
      wakewordRecorderRef.current = recorder;
      recorder
        .start(deviceIdRef.current)
        .catch((err) => settleOnce(() => reject(err)));
    });

    try {
      await detectPromise;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Wake-word listening failed";
      setStatus(`❌ ${msg}`);
      setProcessing(false);
      return;
    } finally {
      wakewordClosingRef.current = true;
      try {
        await wakewordRecorderRef.current?.stop();
      } catch {
        // ignore recorder shutdown noise
      }
      wakewordRecorderRef.current = null;
      if (wakewordSessionRef.current) {
        try {
          await stopBrowserWakewordSession(wakewordSessionRef.current);
        } catch {
          // best-effort cleanup
        }
      }
      wakewordSessionRef.current = null;
      wakewordClosingRef.current = false;
    }

    if (myVersion !== wakewordCancelVersionRef.current) {
      setProcessing(false);
      return;
    }

    if (!wakewordEnabledRef.current || wakewordAbortRef.current) {
      setProcessing(false);
      return;
    }

    setStatus(
      `✅ Wake word detected${detectedLabel ? ` (${detectedLabel})` : ""}` +
      `${detectedScore ? ` score ${detectedScore.toFixed(2)}` : ""}. Speak now.`
    );
    setProcessing(false);
    await start(deviceIdRef.current);
  }, [start]);

  useEffect(() => {
    wakewordEnabledRef.current = wakewordEnabled;
  }, [wakewordEnabled]);

  useEffect(() => {
    if (!wakewordEnabled) {
      wakewordAbortRef.current = true;
      setWakewordListening(false);
      return;
    }
    if (recording || responseActive || processing) {
      return;
    }

    wakewordAbortRef.current = false;
    let cancelled = false;

    const loop = async () => {
      while (!cancelled && !wakewordAbortRef.current && wakewordEnabledRef.current) {
        if (Date.now() < wakewordSuppressUntilRef.current) {
          await sleep(120);
          continue;
        }
        if (wakewordInFlightRef.current || recording || responseActive || processing) {
          await sleep(200);
          continue;
        }
        wakewordInFlightRef.current = true;
        setWakewordListening(true);
        await runWakewordTurn();
        setWakewordListening(false);
        wakewordInFlightRef.current = false;
        if (!wakewordEnabledRef.current || wakewordAbortRef.current) {
          break;
        }
        await sleep(150);
      }
      setWakewordListening(false);
    };

    void loop();

    return () => {
      cancelled = true;
      wakewordAbortRef.current = true;
      wakewordClosingRef.current = true;
      const recorder = wakewordRecorderRef.current;
      wakewordRecorderRef.current = null;
      if (recorder) {
        void recorder.stop().catch(() => undefined);
      }
      const wakeSessionId = wakewordSessionRef.current;
      wakewordSessionRef.current = null;
      if (wakeSessionId) {
        void stopBrowserWakewordSession(wakeSessionId).catch(() => undefined);
      }
      wakewordClosingRef.current = false;
      setWakewordListening(false);
    };
  }, [wakewordEnabled, runWakewordTurn, recording, responseActive, processing]);

  // Instantly clears the current conversation so the next question starts a
  // brand-new session. Because conversation history lives client-side and is
  // forwarded to kiosk-core on each turn, clearing it here resets the session
  // immediately (the backend drops its draft cart when history is empty). No
  // effect while a turn is recording/processing.
  const reset = useCallback(() => {
    if (recording) return;
    recordingRef.current = false;
    // Invalidate any in-flight wake-word turn so it cannot call start().
    wakewordCancelVersionRef.current += 1;
    playerRef.current?.stop();
    setResponseActive(false);
    pendingChunks.current = [];
    sessionIdRef.current = null;
    startPromiseRef.current = null;
    sessionStartErrorRef.current = null;
    const wakeRecorder = wakewordRecorderRef.current;
    wakewordRecorderRef.current = null;
    wakewordClosingRef.current = true;
    if (wakeRecorder) {
      void wakeRecorder.stop().catch(() => undefined);
    }
    const wakeSessionId = wakewordSessionRef.current;
    wakewordSessionRef.current = null;
    if (wakeSessionId) {
      void stopBrowserWakewordSession(wakeSessionId).catch(() => undefined);
    }
    wakewordClosingRef.current = false;
    setProcessing(false);
    setMessages([]);
    setPartialUser("");
    setPartialAssistant("");
    setSessionPerf({ ttstMs: null, endToEndMs: null, rtf: null });
    setStatus(
      wakewordEnabledRef.current
        ? `Idle — say \"${WAKEWORD.model}\" to begin.`
        : "Idle — tap the mic to ask a question."
    );
    // Prevent immediate false wake-word retrigger right after reset.
    wakewordSuppressUntilRef.current = Date.now() + 8000;
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
    processing,
    wakewordEnabled,
    wakewordListening,
    wakewordScore,
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
    sendText,
    setWakewordEnabled: setWakewordEnabledSafe,
    reset,
  };
}
