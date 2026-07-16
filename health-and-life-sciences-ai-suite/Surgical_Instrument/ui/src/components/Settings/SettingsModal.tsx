import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setActiveDevice, resetDetectionState, patchDetectionState } from '../../redux/slices/detectionSlice';
import { startProcessing, stopProcessing } from '../../redux/slices/appSlice';
import { startAllWorkloads, stopAllWorkloads } from '../../redux/slices/servicesSlice';
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
  const [resetBusy, setResetBusy]         = useState(false);
  const [resetStatus, setResetStatus]     = useState<string>('');
  const [restartBusy, setRestartBusy]     = useState(false);
  const [restartStatus, setRestartStatus] = useState<string>('');

  // Source tab state
  const [videos, setVideos]           = useState<VideoItem[]>([]);
  const [videosDir, setVideosDir]     = useState<string>('/videos');
  const [maxUploadMB, setMaxUploadMB] = useState<number>(500);
  const [activeVideo, setActiveVideo] = useState<string | null>(null); // path currently running
  const [defaultVideo, setDefaultVideo] = useState<string>('');
  const [pendingVideo, setPendingVideo] = useState<string | null>(null); // basename selected in the dropdown
  const [sourceStatus, setSourceStatus] = useState<string>('');
  const [uploadBusy, setUploadBusy]   = useState(false);
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
    setResetStatus('');
    setSourceStatus('');
    setRestartStatus('');
    refreshVideos();
  }, [isOpen, currentDevice, refreshVideos]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  // Derived flags — declared before the early-return so all handlers below
  // (including handleApplyAndRestart) can reference them via closure.
  const deviceDirty = pendingDevice !== currentDevice;

  if (!isOpen) return null;

  // Wait until the backend reports lifecycle in the given set, or timeout.
  const waitForLifecycle = async (want: Set<string>, timeoutMs = 8000): Promise<boolean> => {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      try {
        const snap = await api.getStatusSnapshot();
        if (snap && typeof snap.lifecycle === 'string' && want.has(snap.lifecycle)) {
          return true;
        }
      } catch {
        /* keep polling */
      }
      await new Promise((r) => setTimeout(r, 300));
    }
    return false;
  };

  // Shared stop → (optional /api/reset) → start cycle used by both the
  // "Apply & Restart" (Input Source tab) and "Reset Session & Restart"
  // (Devices tab) buttons. Handles the running / stopped cases uniformly.
  const runRestart = async (opts: {
    setBusy: (b: boolean) => void;
    setStatus: (s: string) => void;
    applyDevice: boolean;      // POST /api/device with pendingDevice
    resetSession: boolean;     // POST /api/reset between stop and start
    applySource: boolean;      // stash pendingKind/pendingVideo/pendingCamera for /api/start
  }): Promise<void> => {
    opts.setBusy(true);
    opts.setStatus('Applying changes…');
    try {
      // 1) Stop first if the pipeline is currently running.
      if (isProcessing) {
        dispatch({ type: 'sse/disconnect' });
        dispatch(stopProcessing());
        dispatch(stopAllWorkloads());
        dispatch(patchDetectionState({ systemStatus: 'stopping' }));
        opts.setStatus('Stopping pipeline…');
        try { await api.stop('all'); } catch { /* fall through to poll */ }
        await waitForLifecycle(new Set(['ready', 'error']));
        dispatch(patchDetectionState({ systemStatus: 'ready' }));
      }

      // 2) Apply device change (backend rejects while running — safe now).
      if (opts.applyDevice && deviceDirty) {
        opts.setStatus('Applying device change…');
        await api.setDevice(pendingDevice);
        dispatch(setActiveDevice(pendingDevice));
      }

      // 3) Clear frozen post-stop KPIs + frame if requested.
      if (opts.resetSession) {
        opts.setStatus('Resetting session…');
        try {
          await api.reset();
          dispatch(resetDetectionState());
          // Preserve the freshly-applied device selection.
          dispatch(setActiveDevice(opts.applyDevice ? pendingDevice : currentDevice));
        } catch (err) {
          // Reset failure shouldn't abort the restart — surface it but continue.
          const msg = err instanceof Error ? err.message : String(err);
          opts.setStatus(`Reset warning: ${msg}`);
        }
      }

      // 4) Queue source change; startWorkloads() will include it in the body.
      if (opts.applySource) {
        let arg: string | null = null;
        if (pendingKind === 'file') {
          arg = pendingVideo ? `${videosDir}/${pendingVideo}` : null;
        } else if (pendingKind === 'basler') {
          arg = pendingCamera;
        }
        if (arg) {
          api.setPendingSource({ kind: pendingKind, arg });
        }
      }

      // 5) Start the pipeline with the new settings.
      opts.setStatus('Starting pipeline…');
      dispatch(startProcessing());
      dispatch(startAllWorkloads());
      dispatch(patchDetectionState({ systemStatus: 'starting' }));
      const resp = await api.start('all');
      if (resp.status === 'starting' || resp.status === 'running' || resp.status === 'ok') {
        const eventsUrl = api.getEventsUrl(['all']);
        dispatch({ type: 'sse/connect', payload: { url: eventsUrl } });
        opts.setStatus('Pipeline restarted');
        setTimeout(() => opts.setStatus(''), 3000);
      } else {
        throw new Error(`Start failed: ${JSON.stringify(resp)}`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      dispatch(stopProcessing());
      dispatch(stopAllWorkloads());
      dispatch(patchDetectionState({ systemStatus: 'ready' }));
      opts.setStatus(`Error: ${msg}`);
    } finally {
      opts.setBusy(false);
    }
  };

  const handleApplyAndRestart = () =>
    runRestart({
      setBusy: setRestartBusy,
      setStatus: setRestartStatus,
      applyDevice: true,
      resetSession: false,
      applySource: true,
    });

  const handleResetAndRestart = () =>
    runRestart({
      setBusy: setResetBusy,
      setStatus: setResetStatus,
      applyDevice: true,
      resetSession: true,
      applySource: true,
    });

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

  return (
    <div className="settings-modal-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-modal-header">
          <h2>Settings</h2>
          <button className="settings-close-btn" onClick={onClose} title="Close (Esc)">×</button>
        </div>

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
                Choose which accelerator runs the polyp-detection model. Clicking
                <strong> Reset Session &amp; Restart</strong> will stop the pipeline (if running),
                switch to the selected device, clear session counters, and start again
                with the current input source.
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
                        disabled={resetBusy}
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
                  onClick={handleResetAndRestart}
                  disabled={resetBusy || restartBusy}
                  title={
                    deviceDirty
                      ? `Stop, switch to ${pendingDevice}, clear the session, and restart the pipeline`
                      : 'Clear session counters and restart the pipeline on the current device + source'
                  }
                >
                  {resetBusy
                    ? 'Restarting…'
                    : (isProcessing ? 'Reset Session & Restart' : 'Reset Session & Start')}
                </button>
                {resetStatus && (
                  <span className={`settings-status-inline ${resetStatus.startsWith('Error') ? 'error' : 'success'}`}>
                    {resetStatus.startsWith('Error') || resetBusy ? resetStatus : '✓ ' + resetStatus}
                  </span>
                )}
              </div>
            </div>
          )}

          {activeTab === 'source' && (
            <div className="settings-section">
              <p className="settings-hint" style={{ marginBottom: 12 }}>
                Pick a video file or a Basler camera, then click
                <strong> Apply &amp; Restart</strong>. If the pipeline is running it will be
                stopped, restarted with the new source, and continue on the currently selected
                inference device.
              </p>

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
                      disabled={uploadBusy || restartBusy}
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
                      disabled={uploadBusy || restartBusy || baslerCams.length === 0}
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
                      disabled={uploadBusy || restartBusy || videos.length === 0}
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
                        disabled={uploadBusy || isProcessing || restartBusy}
                        title={isProcessing ? 'Stop the pipeline first (uploads share the videos volume)' : 'Upload a new video'}
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
                    disabled={restartBusy || baslerCams.length === 0}
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
                  onClick={handleApplyAndRestart}
                  disabled={
                    restartBusy || resetBusy ||
                    (pendingKind === 'file'   && !pendingVideo) ||
                    (pendingKind === 'basler' && !pendingCamera)
                  }
                  title={
                    (pendingKind === 'file'   && !pendingVideo)   ? 'Select a video first'
                    : (pendingKind === 'basler' && !pendingCamera) ? 'Select a camera first'
                    : isProcessing ? 'Stop, apply the new source + device, and restart the pipeline'
                    : 'Start the pipeline with the selected source + device'
                  }
                >
                  {restartBusy
                    ? 'Restarting…'
                    : (isProcessing ? 'Apply & Restart' : 'Apply & Start')}
                </button>
                {restartStatus && (
                  <span className={`settings-status-inline ${restartStatus.startsWith('Error') ? 'error' : 'success'}`}>
                    {restartStatus.startsWith('Error') || restartBusy ? restartStatus : '✓ ' + restartStatus}
                  </span>
                )}
                {sourceStatus && !restartStatus && (
                  <span className={`settings-status-inline ${sourceStatus.startsWith('Error') ? 'error' : 'success'}`}>
                    {sourceStatus.startsWith('Error') ? sourceStatus : '✓ ' + sourceStatus}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="settings-modal-footer">
          <button
            className="settings-btn settings-btn-secondary"
            onClick={onClose}
            disabled={restartBusy || resetBusy}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;
