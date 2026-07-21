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

export default function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [deviceId, setDeviceId] = useState<string>();
  const [ingestedName, setIngestedName] = useState<string>("");

  const {
    recording,
    status,
    messages,
    partialUser,
    partialAssistant,
    micAnalyser,
    responseAnalyser,
    responseActive,
    sessionPerf,
    start,
    stop,
  } = useVoiceSession();
  const micLevel = useAudioLevel(micAnalyser, recording);
  const perfMetrics = usePerformanceMetrics();

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
    <div className="mx-auto flex h-full w-full max-w-[1800px] flex-col gap-4 p-4 lg:px-6">
      {/* Header */}
      <header className="flex items-center justify-between rounded-xl bg-intel-blue px-4 py-3 text-white shadow-sm">
        <div>
          <h1 className="text-xl font-semibold text-white">AI Teaching Assistant</h1>
          <p className="text-xs text-white/80">
            Upload a document, then ask questions with your voice.
          </p>
        </div>
        {ingestedName && (
          <span className="rounded-full border border-white/40 bg-white/15 px-3 py-1 text-xs text-white">
            Knowledge base: {ingestedName}
          </span>
        )}
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[320px_1fr] xl:grid-cols-[320px_minmax(0,1fr)_360px]">
        {/* Left: ingestion + device + preview */}
        <aside className="flex min-h-0 flex-col gap-4">
          <section className="rounded-xl border border-blue-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-black">Knowledge base</h2>
            <IngestionPanel
              files={files}
              onFilesSelected={setFiles}
              onIngested={() => setIngestedName(labelFor(files))}
              disabled={recording}
            />
          </section>

          <section className="rounded-xl border border-blue-200 bg-white p-4">
            <DeviceSelector value={deviceId} onChange={setDeviceId} disabled={recording} />
          </section>

          <section className="min-h-[240px] flex-1">
            <UploadedFiles files={files} onRemove={handleRemoveFile} disabled={recording} />
          </section>
        </aside>

        {/* Center: chat + voice */}
        <main className="flex min-h-0 flex-col gap-4">
          <div className="min-h-[320px] flex-1">
            <Chat
              messages={messages}
              partialUser={partialUser}
              partialAssistant={partialAssistant}
              fileName={files[0]?.name ?? (ingestedName || undefined)}
            />
          </div>

          <section className="rounded-xl border border-blue-200 bg-white p-4">
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
              />
              <div className="flex-1 space-y-2">
                <p className="text-sm text-black/80">{status}</p>
                <Visualizer
                  analyser={micAnalyser}
                  active={recording}
                  color="#0068B5"
                  label="Your voice"
                  compact
                />
              </div>
            </div>
          </section>
        </main>

        {/* Right: metrics */}
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
