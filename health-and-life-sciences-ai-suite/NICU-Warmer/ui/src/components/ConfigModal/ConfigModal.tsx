import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAppSelector } from '../../redux/hooks';
import { api } from '../../services/api';
import type { PipelineConfig } from '../../services/api';
import './ConfigModal.css';

interface ConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type Tab = 'video' | 'roi' | 'devices';

const DEVICE_OPTIONS = ['CPU', 'GPU', 'NPU'] as const;
const DEFAULT_ROI = { top: 0.10, left: 0.30, bottom: 0.56, right: 0.70 };

const ConfigModal: React.FC<ConfigModalProps> = ({ isOpen, onClose }) => {
  const { isProcessing } = useAppSelector((state) => state.app);
  const [activeTab, setActiveTab] = useState<Tab>('video');
  const [config, setConfig] = useState<PipelineConfig | null>(null);
  const [loading, setLoading] = useState(true);

  // Video state
  const [uploadStatus, setUploadStatus] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // ROI state
  const [roi, setRoi] = useState(DEFAULT_ROI);
  const [roiStatus, setRoiStatus] = useState('');

  // Device state
  const [devices, setDevices] = useState({ detect: 'GPU', rppg: 'CPU', action: 'NPU' });
  const [deviceStatus, setDeviceStatus] = useState('');

  // Available devices (5C)
  const [availableDevices, setAvailableDevices] = useState<Record<string, boolean>>({ CPU: true, GPU: true, NPU: true });

  // Pending changes & apply state (5D)
  const [pending, setPending] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyStatus, setApplyStatus] = useState('');

  const disabled = false; // No longer lock editing while running

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      const [c, avail] = await Promise.all([
        api.getConfig(),
        api.getAvailableDevices(),
      ]);
      setConfig(c);
      if (c.roi) setRoi(c.roi);
      if (c.devices) {
        // Auto-correct any device selections that point to unavailable hardware.
        // Fall back to CPU which is always available.
        const corrected = { ...c.devices };
        for (const key of ['detect', 'rppg', 'action'] as const) {
          if (corrected[key] && !avail[corrected[key]]) {
            corrected[key] = 'CPU';
          }
        }
        setDevices(corrected);
      }
      setPending(!!c.pending);
      setAvailableDevices(avail);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) fetchConfig();
  }, [isOpen, fetchConfig]);

  if (!isOpen) return null;

  // ── Video handlers ──

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadStatus('');
    try {
      const res = await api.uploadVideo(file);
      setUploadStatus(`Uploaded: ${res.video_file}`);
      fetchConfig();
    } catch (err: any) {
      setUploadStatus(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleClearVideo = async () => {
    try {
      await api.clearVideo();
      setUploadStatus('');
      if (fileRef.current) fileRef.current.value = '';
      fetchConfig();
    } catch (err: any) {
      setUploadStatus(err.message);
    }
  };

  // ── ROI handlers ──

  const handleRoiSave = async () => {
    setRoiStatus('');
    try {
      await api.setRoi(roi);
      setRoiStatus('saved');
      fetchConfig();
      setTimeout(() => setRoiStatus(''), 2500);
    } catch (err: any) {
      setRoiStatus(err.message);
    }
  };

  const handleRoiReset = async () => {
    try {
      await api.clearRoi();
      setRoi(DEFAULT_ROI);
      setRoiStatus('');
      fetchConfig();
    } catch (err: any) {
      setRoiStatus(err.message);
    }
  };

  // ── Device handlers ──

  const handleDeviceSave = async () => {
    setDeviceStatus('');
    try {
      await api.setDevices(devices);
      setDeviceStatus('saved');
      fetchConfig();
      setTimeout(() => setDeviceStatus(''), 2500);
    } catch (err: any) {
      setDeviceStatus(err.message);
    }
  };

  return (
    <div className="config-modal-overlay" onClick={onClose}>
      <div className="config-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="config-modal-header">
          <h2>Pipeline Configuration</h2>
          <button className="config-close-btn" onClick={onClose}>✕</button>
        </div>

        {/* Pending changes banner */}
        {isProcessing && pending && (
          <div className="config-pending-banner">
            Changes are pending — click <strong>Apply &amp; Restart</strong> to take effect
          </div>
        )}
        {isProcessing && !pending && (
          <div className="config-running-banner">
            Pipeline is running — changes will require a restart to take effect
          </div>
        )}

        {/* Tabs */}
        <div className="config-tabs">
          {([
            { key: 'video' as Tab, label: 'Video Source' },
            { key: 'roi' as Tab, label: 'Face ROI' },
            { key: 'devices' as Tab, label: 'Devices' },
          ]).map(({ key, label }) => (
            <button
              key={key}
              className={`config-tab ${activeTab === key ? 'active' : ''}`}
              onClick={() => setActiveTab(key)}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="config-modal-content">
          {loading ? (
            <div className="config-loading">Loading configuration...</div>
          ) : (
            <>
              {/* ── Video Source ── */}
              {activeTab === 'video' && (
                <div className="config-section">
                  <div className="config-field-group">
                    <label className="config-label">Active Video</label>
                    <div className="config-active-video">
                      <span className="config-video-badge">
                        {config?.video_file ? '📁 ' + config.video_file :  + (config?.default_video || 'Default')}
                      </span>
                      {config?.video_file && (
                        <span className="config-video-custom-tag">Custom</span>
                      )}
                    </div>
                  </div>

                  <div className="config-field-group">
                    <label className="config-label">Upload New Video</label>
                    <p className="config-hint">
                      Supported: .mp4, .avi, .mkv, .mov, .ts (max 500 MB).
                      This video will be used by all pipelines (detection, rPPG, action recognition).
                    </p>
                    <div className="config-upload-row">
                      <input
                        ref={fileRef}
                        type="file"
                        accept=".mp4,.avi,.mkv,.mov,.ts"
                        onChange={handleUpload}
                        disabled={disabled || uploading}
                        className="config-file-input-hidden"
                        id="video-upload"
                      />
                      <button
                        className="config-btn config-btn-secondary config-file-btn"
                        disabled={disabled || uploading}
                        onClick={() => fileRef.current?.click()}
                      >
                        {uploading ? 'Uploading…' : 'Choose File'}
                      </button>
                      {config?.video_file && (
                        <button
                          onClick={handleClearVideo}
                          disabled={disabled}
                          className="config-btn config-btn-secondary"
                        >
                          ✕ Use Default
                        </button>
                      )}
                    </div>
                    {uploading && (
                      <div className="config-progress">
                        <div className="config-progress-bar" />
                      </div>
                    )}
                    {uploadStatus && (
                      <p className={`config-status ${uploadStatus.startsWith('Uploaded') ? 'success' : 'error'}`}>
                        {uploadStatus}
                      </p>
                    )}
                  </div>

                  {config?.video_file && !config?.roi_custom && (
                    <div className="config-notice">
                      <strong>Note:</strong> You uploaded a custom video but haven't set a custom Face ROI.
                      The rPPG pipeline will use the default ROI region, which may not match the face
                      position in your video. Switch to the <em>Face ROI</em> tab to configure it.
                    </div>
                  )}
                </div>
              )}

              {/* ── Face ROI ── */}
              {activeTab === 'roi' && (
                <div className="config-section">
                  <p className="config-hint" style={{ marginBottom: 12 }}>
                    Define the face region-of-interest for rPPG vital signs extraction.
                    Values are normalised coordinates (0.0 – 1.0) of the video frame.
                  </p>

                  <div className="config-roi-layout">
                    {/* Visual preview */}
                    <div className="config-roi-preview">
                      <div className="config-roi-frame">
                        <div
                          className="config-roi-box"
                          style={{
                            top: `${roi.top * 100}%`,
                            left: `${roi.left * 100}%`,
                            width: `${(roi.right - roi.left) * 100}%`,
                            height: `${(roi.bottom - roi.top) * 100}%`,
                          }}
                        >
                          <span className="config-roi-label">Face ROI</span>
                        </div>
                      </div>
                      <div className="config-roi-tag">
                        {config?.roi_custom ? 'Custom ROI' : 'Default ROI'}
                      </div>
                    </div>

                    {/* Input fields */}
                    <div className="config-roi-inputs">
                      {(['top', 'left', 'bottom', 'right'] as const).map((k) => (
                        <div className="config-field-group" key={k}>
                          <label className="config-label">{k.charAt(0).toUpperCase() + k.slice(1)}</label>
                          <input
                            type="number"
                            min="0"
                            max="1"
                            step="0.01"
                            value={roi[k]}
                            onChange={(e) => setRoi({ ...roi, [k]: parseFloat(e.target.value) || 0 })}
                            disabled={disabled}
                            className="config-input"
                          />
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="config-actions">
                    <button
                      onClick={handleRoiSave}
                      disabled={disabled}
                      className="config-btn config-btn-primary"
                    >
                      Save ROI
                    </button>
                    <button
                      onClick={handleRoiReset}
                      disabled={disabled}
                      className="config-btn config-btn-secondary"
                    >
                      Reset to Default
                    </button>
                    {roiStatus && (
                      <span className={`config-status-inline ${roiStatus === 'saved' ? 'success' : 'error'}`}>
                        {roiStatus === 'saved' ? '✓ Saved' : roiStatus}
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* ── Device Assignment ── */}
              {activeTab === 'devices' && (
                <div className="config-section">
                  <p className="config-hint" style={{ marginBottom: 12 }}>
                    Choose which hardware accelerator runs each workload.
                    Optimal defaults: Detection → GPU, rPPG → CPU, Action → NPU.
                  </p>

                  {(!availableDevices.GPU || !availableDevices.NPU) && (
                    <div className="config-device-warning">
                      ⚠️ Limited hardware detected:
                      {!availableDevices.GPU && <span> <strong>GPU</strong> not available</span>}
                      {!availableDevices.GPU && !availableDevices.NPU && <span>,</span>}
                      {!availableDevices.NPU && <span> <strong>NPU</strong> not available</span>}
                      . Greyed-out options cannot be selected.
                    </div>
                  )}

                  <table className="config-device-table">
                    <thead>
                      <tr>
                        <th>Workload</th>
                        <th>Models</th>
                        <th>Device</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="config-workload-name">Detection</td>
                        <td className="config-workload-models">Person / Patient / Latch</td>
                        <td>
                          <select
                            value={devices.detect}
                            onChange={(e) => setDevices({ ...devices, detect: e.target.value })}
                            disabled={disabled}
                            className="config-select"
                          >
                            {DEVICE_OPTIONS.map((d) => (
                              <option key={d} value={d} disabled={!availableDevices[d]}>
                                {d}{!availableDevices[d] ? ' (unavailable)' : ''}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                      <tr>
                        <td className="config-workload-name">rPPG</td>
                        <td className="config-workload-models">MTTS-CAN</td>
                        <td>
                          <select
                            value={devices.rppg}
                            onChange={(e) => setDevices({ ...devices, rppg: e.target.value })}
                            disabled={disabled}
                            className="config-select"
                          >
                            {DEVICE_OPTIONS.map((d) => (
                              <option key={d} value={d} disabled={!availableDevices[d]}>
                                {d}{!availableDevices[d] ? ' (unavailable)' : ''}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                      <tr>
                        <td className="config-workload-name">Action Recognition</td>
                        <td className="config-workload-models">Encoder / Decoder</td>
                        <td>
                          <select
                            value={devices.action}
                            onChange={(e) => setDevices({ ...devices, action: e.target.value })}
                            disabled={disabled}
                            className="config-select"
                          >
                            {DEVICE_OPTIONS.map((d) => (
                              <option key={d} value={d} disabled={!availableDevices[d]}>
                                {d}{!availableDevices[d] ? ' (unavailable)' : ''}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    </tbody>
                  </table>

                  <div className="config-actions">
                    <button
                      onClick={handleDeviceSave}
                      disabled={disabled}
                      className="config-btn config-btn-primary"
                    >
                      Save Devices
                    </button>
                    <button
                      onClick={() => setDevices({ detect: 'GPU', rppg: 'CPU', action: 'NPU' })}
                      disabled={disabled}
                      className="config-btn config-btn-secondary"
                    >
                      Reset to Optimal
                    </button>
                    {deviceStatus && (
                      <span className={`config-status-inline ${deviceStatus === 'saved' ? 'success' : 'error'}`}>
                        {deviceStatus === 'saved' ? '✓ Saved' : deviceStatus}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="config-modal-footer">
          {isProcessing && (
            <button
              className="config-btn config-btn-warning"
              disabled={applying}
              onClick={async () => {
                setApplying(true);
                setApplyStatus('');
                try {
                  const res = await api.applyConfig();
                  setApplyStatus(res.message || 'Restarting...');
                  setPending(false);
                  fetchConfig();
                } catch (err: any) {
                  setApplyStatus(err.message);
                } finally {
                  setApplying(false);
                }
              }}
            >
              {applying ? 'Restarting…' : '⟳ Apply & Restart Pipeline'}
            </button>
          )}
          {applyStatus && (
            <span className={`config-status-inline ${applyStatus.includes('error') || applyStatus.includes('fail') ? 'error' : 'success'}`}>
              {applyStatus}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default ConfigModal;
