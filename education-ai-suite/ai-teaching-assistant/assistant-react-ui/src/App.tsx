import { useEffect, useState } from "react";
import DeviceSelector from "./components/DeviceSelector";
import IngestionPanel from "./components/IngestionPanel";
import UploadedFiles from "./components/UploadedFiles";
import Chat from "./components/Chat";
import MicButton from "./components/MicButton";
import TextInput from "./components/TextInput";
import DualVisualizer from "./components/DualVisualizer";
import SessionResetTimer from "./components/SessionResetTimer";
import MetricsPanel from "./components/MetricsPanel";
import { clearContext, getContextStats, ingestFiles } from "./api";
import {
  clearUploadedFiles,
  loadUploadedFiles,
  saveUploadedFiles,
} from "./persistence/uploadedFiles";
import { INACTIVITY_RESET_MS } from "./config";
import { useAudioLevel } from "./hooks/useAudioLevel";
import { usePerformanceMetrics } from "./hooks/usePerformanceMetrics";
import { useVoiceSession } from "./hooks/useVoiceSession";
import intelLogo from "./assets/Intel-logo-2022.png";

const INGESTED_NAME_KEY = "ata.ingestedName";

export default function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [deviceId, setDeviceId] = useState<string>();
  const [ingestedName, setIngestedName] = useState<string>("");
  const [ingesting, setIngesting] = useState(false);
  // Guards the persistence effects so the initial empty state isn't written
  // back over the stored files before hydration finishes.
  const [hydrated, setHydrated] = useState(false);
  // Status line restored after a refresh (e.g. "2 file(s) ingested · 40 chunks").
  const [restoredStatus, setRestoredStatus] = useState<string>("");

  const labelFor = (list: File[]) =>
    list.length === 1 ? list[0].name : list.length > 1 ? `${list.length} files` : "";

  // Restore the uploaded files (and last ingested label) from a previous
  // session so a page refresh doesn't drop them. The backend keeps the ingested
  // chunks, so if it reports an empty context (e.g. after stop_ata reset it) the
  // stale UI list is cleared to stay in sync.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const stored = await loadUploadedFiles();
        if (stored.length === 0) return;
        let hasChunks = true;
        let chunkCount: number | null = null;
        try {
          const stats = await getContextStats();
          chunkCount = stats.document_count;
          hasChunks = (stats.document_count ?? 0) > 0;
        } catch {
          // Backend not reachable yet; keep the files rather than wiping them.
          hasChunks = true;
        }
        if (cancelled) return;
        if (hasChunks) {
          setFiles(stored);
          setIngestedName(
            localStorage.getItem(INGESTED_NAME_KEY) || labelFor(stored)
          );
          if (chunkCount !== null) {
            setRestoredStatus(
              `${stored.length} file(s) ingested \u00b7 ${chunkCount} chunks`
            );
          }
        } else {
          await clearUploadedFiles();
          localStorage.removeItem(INGESTED_NAME_KEY);
        }
      } finally {
        if (!cancelled) setHydrated(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveUploadedFiles(files).catch(() => {});
  }, [files, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    if (ingestedName) localStorage.setItem(INGESTED_NAME_KEY, ingestedName);
    else localStorage.removeItem(INGESTED_NAME_KEY);
  }, [ingestedName, hydrated]);

  const {
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
    start,
    stop,
    sendText,
    setWakewordEnabled,
    reset,
  } = useVoiceSession(deviceId);
  const micLevel = useAudioLevel(micAnalyser, recording);
  // Pause metrics polling while the assistant response audio is being delivered
  // and played, so it doesn't compete with TTS segment delivery to the UI.
  const perfMetrics = usePerformanceMetrics(responseActive);

  // Removes a file from the batch and re-ingests the remaining files so the
  // knowledge base stays in sync with the visible list. The conversation is
  // reset too so the assistant can no longer answer from the removed file's
  // content that may linger in the chat history.
  const handleRemoveFile = async (index: number) => {
    const remaining = files.filter((_, i) => i !== index);
    setFiles(remaining);
    if (remaining.length === 0) {
      await clearUploadedFiles().catch(() => {});
    }
    try {
      await clearContext();
      if (remaining.length > 0) {
        await ingestFiles(remaining);
      }
      setIngestedName(labelFor(remaining));
    } catch {
      // Leave the list as-is; the next upload/re-ingest will reconcile state.
    }
    reset();
  };

  return (
    <div className="flex h-full w-full flex-col gap-4 p-4 lg:px-6">
      {/* Header */}
      <header className="flex items-center justify-between rounded-xl bg-intel-blue px-4 py-3 text-white shadow-xl">
        <div>
          <h1 className="text-xl font-semibold text-white">AI Teaching Assistant</h1>
          <p className="text-xs text-white/80">
            Upload a document, then ask questions with your voice.
          </p>
        </div>
        <img src={intelLogo} alt="Intel" className="h-9 w-auto shrink-0" />
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[320px_1fr] xl:grid-cols-[320px_minmax(0,1fr)_360px]">
        {/* Left column: microphone tile, knowledge base tile, uploaded files */}
        <aside className="flex min-h-0 flex-col gap-2">
          <section className="rounded-xl border border-blue-200 bg-white p-4 shadow-xl">
            <DeviceSelector value={deviceId} onChange={setDeviceId} disabled={recording} />
            <div className="mt-3 border-t border-blue-100 pt-3">
              <label className="flex cursor-pointer items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-black">Wake-word mode</p>
                </div>
                <span className="relative inline-flex h-6 w-11 shrink-0 items-center">
                  <input
                    type="checkbox"
                    checked={wakewordEnabled}
                    onChange={(e) => setWakewordEnabled(e.target.checked)}
                    disabled={recording}
                    className="peer sr-only"
                  />
                  <span className="absolute inset-0 rounded-full bg-gray-300 transition-colors peer-checked:bg-intel-blue peer-disabled:opacity-50" />
                  <span className="absolute left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform peer-checked:translate-x-5" />
                </span>
              </label>
              {wakewordListening && (
                <p className="mt-2 text-xs font-medium text-intel-blue">Listening for wake word...</p>
              )}
              <p className="mt-2 text-xs text-black/70">
                score: <span className="font-semibold text-intel-blue">{wakewordScore.toFixed(2)}</span>
              </p>
            </div>
          </section>

          <section className="rounded-xl border border-blue-200 bg-white p-4 shadow-xl">
            <h2 className="mb-3 text-sm font-semibold text-black">Knowledge base</h2>
            <IngestionPanel
              files={files}
              onFilesSelected={setFiles}
              onIngested={(topic) => setIngestedName(topic ?? labelFor(files))}
              onBusyChange={setIngesting}
              disabled={recording}
              initialMessage={restoredStatus || undefined}
            />
          </section>

          <UploadedFiles files={files} onRemove={handleRemoveFile} disabled={recording} />
        </aside>

        {/* Center tile: chat sub-tile + voice sub-tile */}
        <main className="flex min-h-0 flex-col gap-2 rounded-xl border border-blue-200 bg-white p-4 shadow-xl">
          <div className="flex min-h-[320px] flex-1 flex-col">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-intel-blue text-sm font-bold text-white">
                  J
                </span>
                <h2 className="text-base font-semibold text-black">Jarvis</h2>
              </div>
              <div className="flex items-center gap-3">
                {resetIn !== null && (
                  <SessionResetTimer remaining={resetIn} total={INACTIVITY_RESET_MS / 1000} />
                )}
                <button
                  type="button"
                  onClick={reset}
                  disabled={recording}
                  title="Start a new conversation"
                  className="shrink-0 rounded-lg border-2 border-slate-200 px-4 py-2 text-sm font-semibold text-intel-blue shadow-sm transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  New session
                </button>
              </div>
            </div>
            <div className="min-h-0 flex-1">
              <Chat
                messages={messages}
                partialUser={partialUser}
                partialAssistant={partialAssistant}
                fileName={ingestedName || undefined}
                ingesting={ingesting}
                footer={
                  <DualVisualizer
                    userAnalyser={micAnalyser}
                    userActive={recording}
                    assistantAnalyser={responseAnalyser}
                    assistantActive={responseActive}
                    userColor="#0068B5"
                    assistantColor="#16A34A"
                    compact
                  />
                }
              />
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 shadow-md">
            <p className="text-sm text-black/80">{status}</p>

            <div className="mt-4">
              <TextInput
                onSend={sendText}
                disabled={processing || wakewordListening}
                recording={recording}
                onStop={stop}
                trailing={
                  <MicButton
                    recording={false}
                    inputLevel={micLevel}
                    onStart={() => start(deviceId)}
                    onStop={stop}
                    disabled={recording || wakewordListening || (wakewordEnabled && !recording)}
                  />
                }
              />
            </div>
          </div>
        </main>

        {/* Right tile: metrics */}
        <div className="min-h-0 xl:row-span-1">
          <MetricsPanel
            metrics={perfMetrics}
            sessionPerf={sessionPerf}
          />
        </div>
      </div>
    </div>
  );
}
