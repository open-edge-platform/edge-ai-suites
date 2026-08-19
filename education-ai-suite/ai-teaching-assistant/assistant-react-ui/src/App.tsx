import { useState } from "react";
import DeviceSelector from "./components/DeviceSelector";
import IngestionPanel from "./components/IngestionPanel";
import UploadedFiles from "./components/UploadedFiles";
import Chat from "./components/Chat";
import MicButton from "./components/MicButton";
import Visualizer from "./components/Visualizer";
import MetricsPanel from "./components/MetricsPanel";
import { clearContext, ingestFiles } from "./api";
import { useAudioLevel } from "./hooks/useAudioLevel";
import { usePerformanceMetrics } from "./hooks/usePerformanceMetrics";
import { useVoiceSession } from "./hooks/useVoiceSession";
import intelLogo from "./assets/Intel-logo-2022.png";

export default function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [deviceId, setDeviceId] = useState<string>();
  const [ingestedName, setIngestedName] = useState<string>("");

  const {
    recording,
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
    setWakewordEnabled,
    reset,
  } = useVoiceSession(deviceId);
  const micLevel = useAudioLevel(micAnalyser, recording);
  // Pause metrics polling while the assistant response audio is being delivered
  // and played, so it doesn't compete with TTS segment delivery to the UI.
  const perfMetrics = usePerformanceMetrics(responseActive);

  const labelFor = (list: File[]) =>
    list.length === 1 ? list[0].name : list.length > 1 ? `${list.length} files` : "";

  // Removes a file from the batch and re-ingests the remaining files so the
  // knowledge base stays in sync with the visible list.
  const handleRemoveFile = async (index: number) => {
    const remaining = files.filter((_, i) => i !== index);
    setFiles(remaining);
    try {
      await clearContext();
      if (remaining.length > 0) {
        await ingestFiles(remaining);
      }
      setIngestedName(labelFor(remaining));
    } catch {
      // Leave the list as-is; the next upload/re-ingest will reconcile state.
    }
  };

  return (
    <div className="flex h-full w-full flex-col gap-4 p-4 lg:px-6">
      {/* Header */}
      <header className="flex items-center justify-between rounded-xl bg-intel-blue px-4 py-3 text-white shadow-sm">
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
        <aside className="flex min-h-0 flex-col gap-4">
          <section className="rounded-xl border border-blue-200 bg-white p-4">
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

          <section className="rounded-xl border border-blue-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-black">Knowledge base</h2>
            <IngestionPanel
              files={files}
              onFilesSelected={setFiles}
              onIngested={() => setIngestedName(labelFor(files))}
              disabled={recording}
            />
          </section>

          <section className="min-h-[240px] flex-1">
            <UploadedFiles files={files} onRemove={handleRemoveFile} disabled={recording} />
          </section>
        </aside>

        {/* Center tile: chat sub-tile + voice sub-tile */}
        <main className="flex min-h-0 flex-col gap-4 rounded-xl border border-blue-200 bg-white p-4">
          <div className="min-h-[320px] flex-1">
            <Chat
              messages={messages}
              partialUser={partialUser}
              partialAssistant={partialAssistant}
              fileName={files[0]?.name ?? (ingestedName || undefined)}
            />
          </div>

          <section className="rounded-lg border border-blue-100 bg-slate-50 p-4">
            <div className="grid grid-cols-1 gap-4">
              <Visualizer
                analyser={responseAnalyser}
                active={responseActive}
                color="#2563EB"
                label="Assistant response"
              />
            </div>

            <div className="mt-4 flex items-center gap-4">
              <MicButton
                recording={recording}
                inputLevel={micLevel}
                onStart={() => start(deviceId)}
                onStop={stop}
                disabled={wakewordListening || (wakewordEnabled && !recording)}
              />
              <div className="flex-1 space-y-2">
                <p className="text-sm text-black/80">{status}</p>
                <div className="flex items-end gap-4">
                  <div className="flex-1">
                    <Visualizer
                      analyser={micAnalyser}
                      active={recording}
                      color="#0068B5"
                      label="Your voice"
                      compact
                    />
                  </div>
                  <button
                    type="button"
                    onClick={reset}
                    disabled={recording}
                    title="Start a new conversation"
                    className="shrink-0 rounded-lg border border-blue-200 px-4 py-2 text-sm font-semibold text-intel-blue transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    New session
                  </button>
                  {resetIn !== null && (
                    <span
                      title="Conversation auto-resets when the timer reaches zero"
                      className="shrink-0 tabular-nums text-sm font-medium text-black/60"
                    >
                      Auto-reset in {resetIn}s
                    </span>
                  )}
                </div>
              </div>
            </div>
          </section>
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
