import type { SessionPerfSnapshot } from "../types";
import type { MetricsState } from "../hooks/usePerformanceMetrics";

interface Props {
  metrics: MetricsState;
  sessionPerf: SessionPerfSnapshot;
}

function formatMs(value: number | null): string {
  return value === null ? "--" : `${Math.round(value)} ms`;
}

function formatPct(value: number | null): string {
  return value === null ? "--" : `${value.toFixed(1)}%`;
}

function formatRate(value: number | null): string {
  return value === null ? "--" : value.toFixed(2);
}

function sparkPath(values: number[], width: number, height: number): string {
  if (values.length === 0) return "";
  // Fixed 0-100 domain so the line can be read against the reference grid.
  const toY = (v: number) => height - (Math.max(0, Math.min(100, v)) / 100) * height;
  if (values.length === 1) {
    const y = toY(values[0]);
    return `M 0 ${y.toFixed(2)} L ${width} ${y.toFixed(2)}`;
  }

  return values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = toY(v);
      return `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function Sparkline({ values, color }: { values: number[]; color: string }) {
  const width = 160;
  const height = 80;
  const d = sparkPath(values, width, height);
  // Reference lines at 0, 25, 50, 75, 100 percent.
  const ticks = [0, 25, 50, 75, 100];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="h-20 w-full rounded border border-blue-200 bg-white"
    >
      {ticks.map((t) => {
        const y = height - (t / 100) * height;
        return (
          <g key={t}>
            <line
              x1={0}
              y1={y}
              x2={width}
              y2={y}
              stroke="#e5e7eb"
              strokeWidth={t === 0 || t === 100 ? 1 : 0.5}
            />
            <text x={2} y={y - 1.5} fontSize={7} fill="#9ca3af">
              {t}
            </text>
          </g>
        );
      })}
      {d ? <path d={d} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" /> : null}
    </svg>
  );
}

function MetricCard({
  label,
  value,
  values,
  color,
}: {
  label: string;
  value: string;
  values: number[];
  color: string;
}) {
  return (
    <div className="space-y-1 rounded-lg border border-blue-200 bg-white p-2">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="text-black/70">{label}</span>
        <span className="font-semibold text-black">{value}</span>
      </div>
      <Sparkline values={values} color={color} />
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-blue-100 py-1 last:border-b-0">
      <span className="text-xs text-black/70">{label}</span>
      <span className="text-xs font-semibold text-black">{value}</span>
    </div>
  );
}

export default function MetricsPanel({ metrics, sessionPerf }: Props) {
  return (
    <section className="h-full min-h-0 overflow-y-auto rounded-xl border border-blue-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-black">Performance Metrics</h2>
        {metrics.error && <span className="text-[11px] text-black/60">{metrics.error}</span>}
      </div>

      <div className="space-y-2">
        <div className="text-xs font-medium text-black/80">Hardware</div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-1">
          <MetricCard
            label="CPU Usage"
            value={formatPct(metrics.current.cpu)}
            values={metrics.hardware.cpu}
            color="#1d4ed8"
          />
          <MetricCard
            label="GPU Usage"
            value={formatPct(metrics.current.gpu)}
            values={metrics.hardware.gpu}
            color="#dc2626"
          />
          <MetricCard
            label="NPU Usage"
            value={formatPct(metrics.current.npu)}
            values={metrics.hardware.npu}
            color="#16a34a"
          />
          <MetricCard
            label="Memory Usage"
            value={formatPct(metrics.current.memoryPct)}
            values={metrics.hardware.memoryPct}
            color="#eab308"
          />
        </div>
      </div>

      <div className="mt-4 space-y-2">
        <div className="text-xs font-medium text-black/80">Service Latency</div>
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-2">
          <InfoRow label="ASR Latency" value={formatMs(metrics.current.asrMs)} />
          <InfoRow label="RAG Retrieval" value={formatMs(metrics.current.retrievalMs)} />
          <InfoRow label="RAG LLM" value={formatMs(metrics.current.llmMs)} />
          <InfoRow label="RAG TTFT" value={formatMs(metrics.current.ttftMs)} />
          <InfoRow label="TTS Latency" value={formatMs(metrics.current.ttsMs)} />
          <InfoRow label="Tokens/sec" value={formatRate(metrics.current.tokensPerSec)} />
        </div>
      </div>

      <div className="mt-4 space-y-2">
        <div className="text-xs font-medium text-black/80">Session Timing</div>
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-2">
          <InfoRow label="TTST" value={formatMs(sessionPerf.ttstMs)} />
          <InfoRow label="End-to-End" value={formatMs(sessionPerf.endToEndMs)} />
          <InfoRow label="RTF" value={sessionPerf.rtf === null ? "--" : sessionPerf.rtf.toFixed(3)} />
        </div>
      </div>
    </section>
  );
}
