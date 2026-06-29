import { useAppSelector } from '../store';
import './RightPanel.css';

function Tile({
  label,
  value,
  unit,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  unit?: string;
  tone?: 'neutral' | 'ok' | 'warn' | 'err';
}) {
  return (
    <div className={`tile tone-${tone}`}>
      <div className="tile-label">{label}</div>
      <div className="tile-value">
        <span className="tile-num">{value}</span>
        {unit && <span className="tile-unit">{unit}</span>}
      </div>
    </div>
  );
}

function Bar({ label, pct, tone = 'neutral' }: { label: string; pct: number; tone?: 'neutral' | 'ok' | 'warn' | 'err' }) {
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <div className="bar-row">
      <div className="bar-header">
        <span className="bar-label">{label}</span>
        <span className="bar-pct">{clamped.toFixed(0)}%</span>
      </div>
      <div className="bar-track">
        <div className={`bar-fill tone-${tone}`} style={{ width: `${clamped}%` }} />
      </div>
    </div>
  );
}

export default function RightPanel() {
  const pipeline = useAppSelector((s) => s.metrics.pipeline);
  const system   = useAppSelector((s) => s.metrics.system);

  // p99 ≤ 16.6 ms = 60 fps headroom → ok
  // 16.6 < p99 ≤ 30 ms = within E2E budget → warn (we're spending budget on inference)
  // > 30 ms = exceeds budget → err
  const latencyTone =
    pipeline.latencyP99Ms === 0     ? 'neutral'
    : pipeline.latencyP99Ms <= 16.6 ? 'ok'
    : pipeline.latencyP99Ms <= 30   ? 'warn'
    : 'err';

  const lateTone =
    pipeline.lateFramePct === 0   ? 'neutral'
    : pipeline.lateFramePct <= 1  ? 'ok'
    : pipeline.lateFramePct <= 5  ? 'warn'
    : 'err';

  return (
    <aside className="panel right-panel" aria-label="Live KPIs">
      <h3 className="panel-title">Pipeline KPIs</h3>
      <div className="tile-grid">
        <Tile label="FPS"          value={pipeline.fps.toFixed(1)} />
        <Tile label="p99 latency"  value={pipeline.latencyP99Ms.toFixed(1)} unit="ms" tone={latencyTone} />
        <Tile label="p50 latency"  value={pipeline.latencyP50Ms.toFixed(1)} unit="ms" />
        <Tile label="Late frames"  value={pipeline.lateFramePct.toFixed(1)} unit="%" tone={lateTone} />
        <Tile label="Detections"   value={String(pipeline.detectionCount)} />
        <Tile label="Confidence"   value={pipeline.lastConfidence.toFixed(2)} />
      </div>

      <h3 className="panel-title">System utilisation</h3>
      <div className="bar-stack">
        <Bar label="CPU"     pct={system.cpuPct} tone={system.cpuPct > 85 ? 'warn' : 'neutral'} />
        <Bar label="Arc GPU" pct={system.gpuPct} tone={system.gpuPct > 90 ? 'warn' : 'neutral'} />
        <Bar label="NPU"     pct={system.npuPct} tone={system.npuPct > 90 ? 'warn' : 'neutral'} />
      </div>

      {system.memTotalGib > 0 && (
        <div className="mem-row">
          <span className="bar-label">Memory</span>
          <span className="mem-val">
            {system.memUsedGib.toFixed(1)} / {system.memTotalGib.toFixed(1)} GiB
          </span>
        </div>
      )}
    </aside>
  );
}
