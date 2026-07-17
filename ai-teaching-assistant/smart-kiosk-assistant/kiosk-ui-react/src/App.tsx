import { useState } from "react";
import DeviceSelector from "./components/DeviceSelector";
import IngestionPanel from "./components/IngestionPanel";
import FilePreview from "./components/FilePreview";
import Chat from "./components/Chat";
import MicButton from "./components/MicButton";
import Visualizer from "./components/Visualizer";
import MetricsPanel from "./components/MetricsPanel";
import { useAudioLevel } from "./hooks/useAudioLevel";
import { usePerformanceMetrics } from "./hooks/usePerformanceMetrics";
import { useVoiceSession } from "./hooks/useVoiceSession";

export default function App() {
  const [file, setFile] = useState<File | null>(null);
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

  return (
    <div className="mx-auto flex h-full w-full max-w-[1800px] flex-col gap-4 p-4 lg:px-6">
      {/* Header */}
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-black">AI Teaching Assistant</h1>
          <p className="text-xs text-black/70">
            Upload a document, then ask questions with your voice.
          </p>
        </div>
        {ingestedName && (
          <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs text-blue-700">
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
              file={file}
              onFileSelected={setFile}
              onIngested={() => setIngestedName(file?.name ?? "")}
              disabled={recording}
            />
          </section>

          <section className="rounded-xl border border-blue-200 bg-white p-4">
            <DeviceSelector value={deviceId} onChange={setDeviceId} disabled={recording} />
          </section>

          <section className="min-h-[240px] flex-1">
            <FilePreview file={file} />
          </section>
        </aside>

        {/* Center: chat + voice */}
        <main className="flex min-h-0 flex-col gap-4">
          <div className="min-h-[320px] flex-1">
            <Chat
              messages={messages}
              partialUser={partialUser}
              partialAssistant={partialAssistant}
              fileName={file?.name ?? (ingestedName || undefined)}
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
