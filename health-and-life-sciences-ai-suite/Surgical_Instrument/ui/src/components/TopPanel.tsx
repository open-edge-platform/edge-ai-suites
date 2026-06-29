import { useAppDispatch, useAppSelector } from '../store';
import { api } from '../services/api';
import { setDevice, setInflight, setLastError, type Device } from '../store/slices/controlSlice';
import './TopPanel.css';

const DEVICES: Device[] = ['CPU', 'GPU', 'NPU'];

export default function TopPanel() {
  const dispatch = useAppDispatch();
  const { device, source, threshold, inflightAction, lastError } = useAppSelector((s) => s.control);
  const lifecycle = useAppSelector((s) => s.status.lifecycle);

  const isRunning = lifecycle === 'RUNNING' || lifecycle === 'STARTING';
  const canStart  = !isRunning && inflightAction === 'idle' &&
                    (lifecycle === 'READY' || lifecycle === 'UNKNOWN' || lifecycle === 'ERROR');
  const canStop   = isRunning && inflightAction === 'idle';

  const onStart = async () => {
    dispatch(setInflight('starting'));
    dispatch(setLastError(null));
    try {
      await api.start({ device, source, threshold });
    } catch (e) {
      dispatch(setLastError(e instanceof Error ? e.message : String(e)));
    } finally {
      dispatch(setInflight('idle'));
    }
  };

  const onStop = async () => {
    dispatch(setInflight('stopping'));
    dispatch(setLastError(null));
    try {
      await api.stop();
    } catch (e) {
      dispatch(setLastError(e instanceof Error ? e.message : String(e)));
    } finally {
      dispatch(setInflight('idle'));
    }
  };

  return (
    <div className="topbar">
      <div className="topbar-group">
        <span className="topbar-label">Device</span>
        <div className="device-select" role="radiogroup" aria-label="Inference device">
          {DEVICES.map((d) => (
            <button
              key={d}
              role="radio"
              aria-checked={device === d}
              className={`device-btn ${device === d ? 'is-active' : ''}`}
              onClick={() => dispatch(setDevice(d))}
              disabled={isRunning}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      <div className="topbar-group">
        <button
          className="btn btn-primary"
          onClick={onStart}
          disabled={!canStart}
          title={canStart ? 'Start pipeline' : 'Pipeline already running'}
        >
          {inflightAction === 'starting' ? 'Starting…' : 'Start'}
        </button>
        <button
          className="btn btn-secondary"
          onClick={onStop}
          disabled={!canStop}
          title={canStop ? 'Stop pipeline' : 'No active pipeline'}
        >
          {inflightAction === 'stopping' ? 'Stopping…' : 'Stop'}
        </button>
      </div>

      <div className="topbar-group topbar-status">
        <span className={`pill pill-${lifecycle.toLowerCase()}`}>{lifecycle}</span>
        {lastError && <span className="topbar-error" title={lastError}>⚠ {lastError.slice(0, 60)}</span>}
      </div>
    </div>
  );
}
