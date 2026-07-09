import React, { useState, useEffect, useCallback } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setActiveDevice, resetDetectionState } from '../../redux/slices/detectionSlice';
import { api, type Device } from '../../services/api';
import '../../assets/css/SettingsModal.css';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type Tab = 'source' | 'devices';

const DEVICE_OPTIONS: Device[] = ['GPU', 'CPU', 'NPU'];

const buildDeviceHelp = (platform: Record<string, string> | null): Record<Device, string> => ({
  GPU: platform && platform.iGPU
    ? 'Runs on ' + platform.iGPU + ' via OpenVINO (recommended for polyp detection).'
    : 'Runs on the integrated GPU via OpenVINO (recommended for polyp detection).',
  CPU: platform && platform.Processor
    ? 'Runs on ' + platform.Processor + ' as a fallback path (highest latency).'
    : 'Runs on the host CPU as a fallback path (highest latency).',
  NPU: platform && platform.NPU
    ? 'Runs on ' + platform.NPU + ' for lowest power sustained inference.'
    : 'Runs on the Intel AI Boost NPU for lowest power sustained inference.',
});

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const dispatch = useAppDispatch();
  const systemStatus = useAppSelector((state) => state.detection.data.systemStatus);
  const modelInfo    = useAppSelector((state) => state.detection.data.modelInfo);
  const pipelinePerf = useAppSelector((state) => state.detection.data.pipelinePerformance);
  const platform     = useAppSelector((state) => state.metrics.platform);

  const deviceHelp = buildDeviceHelp(platform as Record<string, string> | null);

  const isProcessing = systemStatus === 'running' || systemStatus === 'starting';

  const currentDevice: Device =
    (modelInfo?.device as Device) ||
    (pipelinePerf?.workloads?.[0]?.device as Device) ||
    'GPU';

  const [activeTab, setActiveTab]         = useState<Tab>('source');
  const [pendingDevice, setPendingDevice] = useState<Device>(currentDevice);
  const [deviceBusy, setDeviceBusy]       = useState(false);
  const [deviceStatus, setDeviceStatus]   = useState<string>('');
  const [resetBusy, setResetBusy]         = useState(false);
  const [resetStatus, setResetStatus]     = useState<string>('');

  // Source (read-only for now — full picker lands in a follow-up slice
  // once GET /api/videos + GET /api/devices/cameras are wired up).
  const [sourceArg,  setSourceArg]  = useState<string | null>(null);

  const refreshSource = useCallback(async () => {
    try {
      const cfg = await api.getConfig();
      setSourceArg(cfg.video_file || cfg.default_video || null);
    } catch {
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
          <div className="settings-running-banner">
            Pipeline is running — stop it before changing hardware or resetting the session.
          </div>
        )}

        <div className="settings-tabs">
          <button
            className={`settings-tab ${activeTab === 'source' ? 'active' : ''}`}
            onClick={() => setActiveTab('source')}
          >
            Input Source
          </button>
          <button
            className={`settings-tab ${activeTab === 'devices' ? 'active' : ''}`}
            onClick={() => setActiveTab('devices')}
          >
            Devices
          </button>
        </div>

        <div className="settings-modal-content">
          {activeTab === 'devices' && (
            <div className="settings-section">
              <p className="settings-hint" style={{ marginBottom: 12 }}>
                Choose which hardware accelerator runs the polyp-detection model.
                Change is applied when you click Save.
              </p>

              <table className="settings-device-table">
                <thead>
                  <tr>
                    <th>Workload</th>
                    <th>Model</th>
                    <th>Device</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="settings-workload-name">Detection</td>
                    <td className="settings-workload-models">Polyp detector (YOLOv9)</td>
                    <td>
                      <select
                        className="settings-select"
                        value={pendingDevice}
                        onChange={(e) => setPendingDevice(e.target.value as Device)}
                        disabled={isProcessing || deviceBusy}
                      >
                        {DEVICE_OPTIONS.map((d) => (
                          <option key={d} value={d}>{d}{currentDevice === d ? ' (current)' : ''}</option>
                        ))}
                      </select>
                      <div className="settings-device-help">{deviceHelp[pendingDevice]}</div>
                    </td>
                  </tr>
                </tbody>
              </table>

              <div className="settings-actions">
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
                <button
                  className="settings-btn settings-btn-secondary"
                  onClick={handleReset}
                  disabled={resetBusy || isProcessing}
                  title={isProcessing ? 'Stop the pipeline first' : 'Clear the last session'}
                >
                  {resetBusy ? 'Resetting…' : 'Reset session'}
                </button>
                {deviceStatus && (
                  <span className={`settings-status-inline ${deviceStatus.startsWith('Error') ? 'error' : 'success'}`}>
                    {deviceStatus.startsWith('Error') ? deviceStatus : '✓ ' + deviceStatus}
                  </span>
                )}
                {resetStatus && !deviceStatus && (
                  <span className={`settings-status-inline ${resetStatus.startsWith('Error') ? 'error' : 'success'}`}>
                    {resetStatus.startsWith('Error') ? resetStatus : '✓ ' + resetStatus}
                  </span>
                )}
              </div>
            </div>
          )}

          {activeTab === 'source' && (
            <div className="settings-section">
              <div className="settings-field-group">
                <label className="settings-label">Active Video</label>
                <div className="settings-active-video">
                  <span className="settings-video-badge">
                    📁 {sourceArg ?? '—'}
                  </span>
                  <span className="settings-video-default-tag">Default</span>
                </div>
              </div>

              <div className="settings-field-group">
                <label className="settings-label">Change Input</label>
                <p className="settings-hint">
                  The backend already accepts a source override on <code>POST /api/start</code>:
                  {' '}<code>{'{ "device": "GPU", "source": { "kind": "file|v4l2|basler", "arg": "..." } }'}</code>.
                </p>
                <div className="settings-notice">
                  <strong>Coming next:</strong> UI dropdowns for available video files and attached cameras.
                  Depends on <code>GET /api/videos</code> (pending) and <code>GET /api/devices/cameras</code>
                  (shipped — returns empty on hosts with no camera).
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
