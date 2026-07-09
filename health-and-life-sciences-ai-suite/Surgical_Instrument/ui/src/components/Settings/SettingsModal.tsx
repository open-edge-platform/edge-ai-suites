import React, { useState, useEffect, useCallback } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setActiveDevice, resetDetectionState } from '../../redux/slices/detectionSlice';
import { api, type Device } from '../../services/api';
import '../../assets/css/SettingsModal.css';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type Tab = 'devices' | 'source';

const DEVICE_OPTIONS: Device[] = ['GPU', 'CPU', 'NPU'];

const DEVICE_HELP: Record<Device, string> = {
  GPU: 'Intel Arc iGPU via OpenVINO (recommended).',
  CPU: 'Fallback path — highest latency.',
  NPU: 'Intel AI Boost NPU — lowest power.',
};

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const dispatch = useAppDispatch();
  const systemStatus = useAppSelector((state) => state.detection.data.systemStatus);
  const modelInfo    = useAppSelector((state) => state.detection.data.modelInfo);
  const pipelinePerf = useAppSelector((state) => state.detection.data.pipelinePerformance);

  const isProcessing = systemStatus === 'running' || systemStatus === 'starting';

  const currentDevice: Device =
    (modelInfo?.device as Device) ||
    (pipelinePerf?.workloads?.[0]?.device as Device) ||
    'GPU';

  const [activeTab, setActiveTab]         = useState<Tab>('devices');
  const [pendingDevice, setPendingDevice] = useState<Device>(currentDevice);
  const [deviceBusy, setDeviceBusy]       = useState(false);
  const [deviceStatus, setDeviceStatus]   = useState<string>('');
  const [resetBusy, setResetBusy]         = useState(false);
  const [resetStatus, setResetStatus]     = useState<string>('');

  // Source (read-only for now — full picker lands in a follow-up slice
  // once GET /api/videos + GET /api/devices/cameras are wired up).
  const [sourceKind, setSourceKind] = useState<string | null>(null);
  const [sourceArg,  setSourceArg]  = useState<string | null>(null);

  const refreshSource = useCallback(async () => {
    try {
      const cfg = await api.getConfig();
      // getConfig returns { video_file, default_video, ... }
      setSourceKind('file');
      setSourceArg(cfg.video_file || cfg.default_video || null);
    } catch {
      setSourceKind(null);
      setSourceArg(null);
    }
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    setPendingDevice(currentDevice);
    setDeviceStatus('');
    setResetStatus('');
    refreshSource();
  }, [isOpen, currentDevice, refreshSource]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const deviceDirty = pendingDevice !== currentDevice;

  const handleApplyDevice = async () => {
    if (!deviceDirty || deviceBusy || isProcessing) return;
    setDeviceBusy(true);
    setDeviceStatus('');
    try {
      await api.setDevice(pendingDevice);
      dispatch(setActiveDevice(pendingDevice));
      setDeviceStatus('Saved');
      setTimeout(() => setDeviceStatus(''), 2500);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setDeviceStatus(`Error: ${msg}`);
    } finally {
      setDeviceBusy(false);
    }
  };

  const handleReset = async () => {
    if (resetBusy || isProcessing) return;
    setResetBusy(true);
    setResetStatus('');
    try {
      const dev = currentDevice;
      await api.reset();
      dispatch(resetDetectionState());
      dispatch(setActiveDevice(dev));
      setResetStatus('Session cleared');
      setTimeout(() => setResetStatus(''), 2500);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setResetStatus(`Error: ${msg}`);
    } finally {
      setResetBusy(false);
    }
  };

  return (
    <div className="settings-modal-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-modal-header">
          <h2>Settings</h2>
          <button className="settings-close-btn" onClick={onClose} title="Close (Esc)">×</button>
        </div>

        {isProcessing && (
          <div className="settings-banner settings-banner-running">
            Pipeline is running — stop it before changing hardware or resetting the session.
          </div>
        )}

        <div className="settings-tabs">
          <button
            className={`settings-tab ${activeTab === 'devices' ? 'active' : ''}`}
            onClick={() => setActiveTab('devices')}
          >
            Hardware
          </button>
          <button
            className={`settings-tab ${activeTab === 'source' ? 'active' : ''}`}
            onClick={() => setActiveTab('source')}
          >
            Input Source
          </button>
        </div>

        <div className="settings-modal-content">
          {activeTab === 'devices' && (
            <div className="settings-section">
              <div className="settings-section-title">Inference device</div>
              <div className="settings-section-sub">
                Choose where the polyp-detection model runs. Change is applied when you click Save.
              </div>

              <div className="settings-device-grid">
                {DEVICE_OPTIONS.map((d) => (
                  <label
                    key={d}
                    className={`settings-device-card ${pendingDevice === d ? 'selected' : ''} ${isProcessing ? 'disabled' : ''}`}
                  >
                    <input
                      type="radio"
                      name="settings-device"
                      value={d}
                      checked={pendingDevice === d}
                      onChange={() => setPendingDevice(d)}
                      disabled={isProcessing || deviceBusy}
                    />
                    <div className="settings-device-name">{d}</div>
                    <div className="settings-device-help">{DEVICE_HELP[d]}</div>
                    {currentDevice === d && (
                      <div className="settings-device-current-tag">current</div>
                    )}
                  </label>
                ))}
              </div>

              <div className="settings-row-actions">
                <button
                  className="settings-btn settings-btn-primary"
                  onClick={handleApplyDevice}
                  disabled={!deviceDirty || deviceBusy || isProcessing}
                  title={
                    isProcessing ? 'Stop the pipeline first'
                    : !deviceDirty ? 'No change to save'
                    : 'Apply device change'
                  }
                >
                  {deviceBusy ? 'Saving…' : 'Save'}
                </button>
                {deviceStatus && (
                  <span className={`settings-inline-status ${deviceStatus.startsWith('Error') ? 'err' : 'ok'}`}>
                    {deviceStatus}
                  </span>
                )}
              </div>

              <hr className="settings-hr" />

              <div className="settings-section-title">Session</div>
              <div className="settings-section-sub">
                Clear the last run's frame + KPIs so you can start fresh with a new device or source.
              </div>
              <div className="settings-row-actions">
                <button
                  className="settings-btn settings-btn-secondary"
                  onClick={handleReset}
                  disabled={resetBusy || isProcessing}
                  title={isProcessing ? 'Stop the pipeline first' : 'Clear the last session'}
                >
                  {resetBusy ? 'Resetting…' : 'Reset session'}
                </button>
                {resetStatus && (
                  <span className={`settings-inline-status ${resetStatus.startsWith('Error') ? 'err' : 'ok'}`}>
                    {resetStatus}
                  </span>
                )}
              </div>
            </div>
          )}

          {activeTab === 'source' && (
            <div className="settings-section">
              <div className="settings-section-title">Current input</div>
              <div className="settings-source-current">
                <div className="settings-source-row">
                  <span className="settings-source-label">Kind</span>
                  <span className="settings-source-value">{sourceKind ?? '—'}</span>
                </div>
                <div className="settings-source-row">
                  <span className="settings-source-label">Path</span>
                  <span className="settings-source-value settings-mono">{sourceArg ?? '—'}</span>
                </div>
              </div>

              <hr className="settings-hr" />

              <div className="settings-section-title">Change input</div>
              <div className="settings-source-placeholder">
                <div style={{ fontWeight: 600, marginBottom: 6 }}>
                  Video upload and camera picker are coming next.
                </div>
                <div style={{ fontSize: 12, lineHeight: 1.55 }}>
                  Today the backend already accepts a source override on <code>POST /api/start</code>:
                  <pre className="settings-code">{`{
  "device": "GPU",
  "source": { "kind": "file|v4l2|basler", "arg": "..." }
}`}</pre>
                  The UI dropdowns for available videos and attached cameras will land in the next slice
                  (needs <code>GET /api/videos</code> + <code>GET /api/devices/cameras</code>).
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="settings-modal-footer">
          <button className="settings-btn settings-btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;
