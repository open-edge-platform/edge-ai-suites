import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setActiveDevice, resetDetectionState } from '../../redux/slices/detectionSlice';
import {
  api,
  type Device,
  type VideoItem,
  type BaslerCamera,
} from '../../services/api';
import '../../assets/css/SettingsModal.css';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type Tab = 'source' | 'devices';
// Customer memo scope: recorded file + live Basler industrial camera.
// v4l2/UVC was a dev-time fallback and is intentionally not surfaced in the UI.
type SourceKind = 'file' | 'basler';

const DEVICE_OPTIONS: Device[] = ['GPU', 'CPU', 'NPU'];

const formatMB = (n: number) => (n / (1024 * 1024)).toFixed(1) + ' MB';

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

  const [activeTab, setActiveTab]         = useState<Tab>('source');
  const [pendingDevice, setPendingDevice] = useState<Device>(currentDevice);
  const [deviceBusy, setDeviceBusy]       = useState(false);
  const [deviceStatus, setDeviceStatus]   = useState<string>('');
  const [resetBusy, setResetBusy]         = useState(false);
  const [resetStatus, setResetStatus]     = useState<string>('');

  // Source tab state
  const [videos, setVideos]           = useState<VideoItem[]>([]);
  const [videosDir, setVideosDir]     = useState<string>('/videos');
  const [maxUploadMB, setMaxUploadMB] = useState<number>(500);
  const [activeVideo, setActiveVideo] = useState<string | null>(null); // path currently running
  const [defaultVideo, setDefaultVideo] = useState<string>('');
  const [pendingVideo, setPendingVideo] = useState<string | null>(null); // basename selected in the dropdown
  const [sourceStatus, setSourceStatus] = useState<string>('');
  const [uploadBusy, setUploadBusy]   = useState(false);
  const [sourceBusy, setSourceBusy]   = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Camera-source state (populated on modal open; empty on hosts with no camera)
  const [pendingKind,   setPendingKind]   = useState<SourceKind>('file');
  const [baslerCams,    setBaslerCams]    = useState<BaslerCamera[]>([]);
  const [baslerNote,    setBaslerNote]    = useState<string | null>(null);
  const [pendingCamera, setPendingCamera] = useState<string | null>(null); // Basler serial number

  const refreshVideos = useCallback(async () => {
    try {
      const [cfg, list, cams] = await Promise.all([
        api.getConfig(),
        api.listVideos(),
        api.listCameras().catch(() => ({ basler: [] } as { basler: BaslerCamera[]; basler_note?: string })),
      ]);
      setVideos(list.videos);
      setVideosDir(list.dir);
      setMaxUploadMB(list.max_upload_mb);
      setActiveVideo(cfg.video_file || null);
      setDefaultVideo(cfg.default_video || '');
      setBaslerCams(cams.basler || []);
      setBaslerNote(cams.basler_note || null);

      // Prime the kind + selection from (pending > running-config > defaults).
      // Any legacy 'v4l2' value coming back from the backend is coerced to 'file'
      // because the UI no longer surfaces v4l2 as a selectable source.
      const pending = api.getPendingSource();
      const rawRunning = (cfg.source?.kind as string | undefined) ?? 'file';
      const rawPending = (pending?.kind as string | undefined);
      const coerce = (k: string | undefined): SourceKind =>
        (k === 'basler' ? 'basler' : 'file');
      const kind: SourceKind = coerce(rawPending) ?? coerce(rawRunning) ?? 'file';
      setPendingKind(kind);

      // Video dropdown initial value
      const pendingName =
        pending && pending.kind === 'file' ? pending.arg.replace(/^.*\//, '') : null;
      const runningName = cfg.video_file ? cfg.video_file.replace(/^.*\//, '') : null;
      setPendingVideo(pendingName ?? runningName ?? list.videos[0]?.name ?? null);

      // Camera dropdown initial value — Basler only
      let cam: string | null = null;
      if (pending && pending.kind === 'basler') {
        cam = pending.arg;
      } else if (kind === 'basler' && (cams.basler || []).length > 0) {
        cam = cams.basler[0].serial;
      }
      setPendingCamera(cam);
    } catch {
      setVideos([]);
      setBaslerCams([]);
      setPendingVideo(null);
      setPendingCamera(null);
    }
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    setPendingDevice(currentDevice);
    setDeviceStatus('');
    setResetStatus('');
    setSourceStatus('');
    refreshVideos();
  }, [isOpen, currentDevice, refreshVideos]);

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

  const handleChooseFile = () => {
    if (uploadBusy || isProcessing) return;
    fileInputRef.current?.click();
  };

  const handleUpload = async (ev: React.ChangeEvent<HTMLInputElement>) => {
    const f = ev.target.files?.[0];
    ev.target.value = ''; // allow re-selecting same name after error
    if (!f) return;
    setUploadBusy(true);
    setSourceStatus('');
    try {
      const res = await api.uploadVideo(f);
      await refreshVideos();
      setPendingVideo(res.name);
      setSourceStatus(`Uploaded ${res.name} (${formatMB(res.size_bytes)})`);
      setTimeout(() => setSourceStatus(''), 3000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setSourceStatus(`Error: ${msg}`);
    } finally {
      setUploadBusy(false);
    }
  };

  const handleApplySource = () => {
    if (sourceBusy || isProcessing) return;
    // Build the outgoing source payload per selected kind.
    let arg: string | null = null;
    if (pendingKind === 'file') {
      if (!pendingVideo) return;
      arg = `${videosDir}/${pendingVideo}`;
    } else if (pendingKind === 'basler') {
      if (!pendingCamera) return;
      arg = pendingCamera;                    // Basler serial number
    }
    if (!arg) return;

    setSourceBusy(true);
    setSourceStatus('');
    // Persist client-side; startWorkloads() will include this in the next
    // POST /api/start body. We don't hit the backend now because it rejects
    // source changes while running (409) and there's no dedicated
    // `POST /api/source` endpoint yet.
    api.setPendingSource({ kind: pendingKind, arg });
    setSourceStatus('Applied on next Start');
    setTimeout(() => setSourceStatus(''), 3000);
    setSourceBusy(false);
  };

  // "Dirty" = pending selection differs from what's actually running now.
  const sourceDirty = (() => {
    const pendingArg =
      pendingKind === 'file'
        ? (pendingVideo ? `${videosDir}/${pendingVideo}` : null)
        : pendingCamera;
    if (!pendingArg) return false;
    // Compare against what /api/config reported. For `file` we compare basenames
    // (activeVideo is the full path); for camera kinds we only know the running
    // source is a camera when config.source.kind agrees.
    const runningName = activeVideo ? activeVideo.replace(/^.*\//, '') : null;
    if (pendingKind === 'file') {
      return pendingVideo !== runningName;
    }
    // For v4l2/basler, dirtiness is "kind changed" or "we don't know the current
    // camera arg" — err on the side of enabling Apply so the user can commit.
    return true;
  })();

  return (
    <div className="settings-modal-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-modal-header">
          <h2>Settings</h2>
          <button className="settings-close-btn" onClick={onClose} title="Close (Esc)">×</button>
        </div>

        {isProcessing && (
          <div className="settings-running-banner">
            Pipeline is running — stop it before changing hardware, source, or resetting the session.
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
                Choose which accelerator runs the polyp-detection model.
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
                    📁 {activeVideo ? activeVideo.replace(/^.*\//, '') : (defaultVideo.replace(/^.*\//, '') || '—')}
                  </span>
                  {!activeVideo && defaultVideo && (
                    <span className="settings-video-default-tag">Default</span>
                  )}
                </div>
              </div>

              <div className="settings-field-group">
                <label className="settings-label">Source type</label>
                <div className="settings-source-kinds">
                  <label className={`settings-source-kind ${pendingKind === 'file' ? 'active' : ''}`}>
                    <input
                      type="radio"
                      name="source-kind"
                      value="file"
                      checked={pendingKind === 'file'}
                      onChange={() => setPendingKind('file')}
                      disabled={isProcessing || uploadBusy}
                    />
                    <span>Video file</span>
                  </label>
                  <label className={`settings-source-kind ${pendingKind === 'basler' ? 'active' : ''} ${baslerCams.length === 0 ? 'disabled' : ''}`}>
                    <input
                      type="radio"
                      name="source-kind"
                      value="basler"
                      checked={pendingKind === 'basler'}
                      onChange={() => {
                        setPendingKind('basler');
                        if (!pendingCamera && baslerCams[0]) setPendingCamera(baslerCams[0].serial);
                      }}
                      disabled={isProcessing || uploadBusy || baslerCams.length === 0}
                    />
                    <span>Basler camera{baslerCams.length === 0 ? ' (none detected)' : ''}</span>
                  </label>
                </div>
              </div>

              {pendingKind === 'file' && (
                <>
                  <div className="settings-field-group">
                    <label className="settings-label">Select a video</label>
                    <select
                      className="settings-select"
                      value={pendingVideo ?? ''}
                      onChange={(e) => setPendingVideo(e.target.value || null)}
                      disabled={isProcessing || uploadBusy || videos.length === 0}
                      style={{ minWidth: 320 }}
                    >
                      {videos.length === 0 && <option value="">(no videos available)</option>}
                      {videos.map((v) => {
                        const runningName = activeVideo ? activeVideo.replace(/^.*\//, '') : null;
                        return (
                          <option key={v.name} value={v.name}>
                            {v.name} — {formatMB(v.size_bytes)}
                            {v.name === runningName ? ' (current)' : ''}
                          </option>
                        );
                      })}
                    </select>
                    <p className="settings-hint" style={{ marginTop: 8 }}>
                      Files live under <code>{videosDir}</code> inside the container (host <code>./videos</code>).
                      New selection takes effect on the next Start.
                    </p>
                  </div>

                  <div className="settings-field-group">
                    <label className="settings-label">Upload a video</label>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".mp4,.mkv,.avi,.mov,.ts,video/*"
                      style={{ display: 'none' }}
                      onChange={handleUpload}
                    />
                    <div className="settings-actions" style={{ marginTop: 0 }}>
                      <button
                        className="settings-btn settings-btn-secondary"
                        onClick={handleChooseFile}
                        disabled={uploadBusy || isProcessing}
                        title={isProcessing ? 'Stop the pipeline first' : 'Upload a new video'}
                      >
                        {uploadBusy ? 'Uploading…' : 'Choose file…'}
                      </button>
                      <span className="settings-hint" style={{ marginLeft: 8 }}>
                        Max {maxUploadMB} MB. Accepted: .mp4 .mkv .avi .mov .ts
                      </span>
                    </div>
                  </div>
                </>
              )}

              {pendingKind === 'basler' && (
                <div className="settings-field-group">
                  <label className="settings-label">Select a Basler camera</label>
                  <select
                    className="settings-select"
                    value={pendingCamera ?? ''}
                    onChange={(e) => setPendingCamera(e.target.value || null)}
                    disabled={isProcessing || baslerCams.length === 0}
                    style={{ minWidth: 320 }}
                  >
                    {baslerCams.length === 0 && <option value="">(no Basler cameras detected)</option>}
                    {baslerCams.map((c) => (
                      <option key={c.serial} value={c.serial}>
                        {c.model} — SN {c.serial} ({c.vendor})
                      </option>
                    ))}
                  </select>
                  {baslerNote && (
                    <p className="settings-hint" style={{ marginTop: 8 }}>
                      <em>{baslerNote}</em>
                    </p>
                  )}
                </div>
              )}

              <div className="settings-actions">
                <button
                  className="settings-btn settings-btn-primary"
                  onClick={handleApplySource}
                  disabled={
                    !sourceDirty || sourceBusy || isProcessing ||
                    (pendingKind === 'file'   && !pendingVideo) ||
                    (pendingKind !== 'file'   && !pendingCamera)
                  }
                  title={
                    isProcessing ? 'Stop the pipeline first'
                    : (pendingKind === 'file' && !pendingVideo) ? 'Select a video first'
                    : (pendingKind !== 'file' && !pendingCamera) ? 'Select a camera first'
                    : !sourceDirty ? 'Selection matches current source'
                    : 'Apply on next Start'
                  }
                >
                  Apply
                </button>
                {sourceStatus && (
                  <span className={`settings-status-inline ${sourceStatus.startsWith('Error') ? 'error' : 'success'}`}>
                    {sourceStatus.startsWith('Error') ? sourceStatus : '✓ ' + sourceStatus}
                  </span>
                )}
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
