import { useAppDispatch, useAppSelector } from '../store';
import { setThreshold, setSource, type Source } from '../store/slices/controlSlice';
import './LeftPanel.css';

const SOURCES: { value: Source; label: string; hint: string }[] = [
  { value: 'file',   label: 'Recorded video', hint: 'Endoscopy clip from /videos' },
  { value: 'basler', label: 'Basler USB3',    hint: 'Live camera (Phase 6)' },
];

export default function LeftPanel() {
  const dispatch = useAppDispatch();
  const { source, threshold, modelName, device } = useAppSelector((s) => s.control);
  const lifecycle = useAppSelector((s) => s.status.lifecycle);

  const locked = lifecycle === 'RUNNING' || lifecycle === 'STARTING';

  return (
    <aside className="panel left-panel" aria-label="Configuration">
      <h3 className="panel-title">Pipeline</h3>

      <div className="lp-row">
        <div className="lp-label">Model</div>
        <div className="lp-value lp-mono">{modelName}</div>
      </div>

      <div className="lp-row">
        <div className="lp-label">Device</div>
        <div className="lp-value">{device}</div>
      </div>

      <h3 className="panel-title">Source</h3>
      <div className="lp-source">
        {SOURCES.map((s) => (
          <label key={s.value} className={`lp-source-opt ${source === s.value ? 'is-active' : ''} ${s.value === 'basler' ? 'is-disabled' : ''}`}>
            <input
              type="radio"
              name="source"
              value={s.value}
              checked={source === s.value}
              onChange={() => dispatch(setSource(s.value))}
              disabled={locked || s.value === 'basler'}
            />
            <span className="lp-source-label">{s.label}</span>
            <span className="lp-source-hint">{s.hint}</span>
          </label>
        ))}
      </div>

      <h3 className="panel-title">Detection threshold</h3>
      <div className="lp-threshold">
        <input
          type="range"
          min={0.05}
          max={0.95}
          step={0.05}
          value={threshold}
          onChange={(e) => dispatch(setThreshold(parseFloat(e.target.value)))}
          disabled={locked}
        />
        <span className="lp-threshold-value">{threshold.toFixed(2)}</span>
      </div>
    </aside>
  );
}
