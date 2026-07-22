import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { startProcessing, stopProcessing } from '../../redux/slices/appSlice';
import { startAllWorkloads, stopAllWorkloads } from '../../redux/slices/servicesSlice';
import { patchDetectionState, resetDetectionState, setActiveDevice } from '../../redux/slices/detectionSlice';
import { api, type BaslerCamera, type Device, type VideoItem } from '../../services/api';
import '../../assets/css/ConfigPanel.css';

type SourceKind = 'file' | 'basler';

const DEVICE_OPTIONS: Device[] = ['GPU', 'CPU', 'NPU'];

const formatMB = (n: number) => `${(n / (1024 * 1024)).toFixed(1)} MB`;

const ConfigPanel: React.FC = () => {
  const dispatch = useAppDispatch();
  const systemStatus = useAppSelector((state) => state.detection.data.systemStatus);
  const modelInfo = useAppSelector((state) => state.detection.data.modelInfo);
  const pipelinePerf = useAppSelector((state) => state.detection.data.pipelinePerformance);

  const isProcessing = systemStatus === 'running' || systemStatus === 'starting';
  const currentDevice: Device = useMemo(
    () => (modelInfo?.device as Device) || (pipelinePerf?.workloads?.[0]?.device as Device) || 'GPU',
    [modelInfo, pipelinePerf],
  );

  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [videosDir, setVideosDir] = useState('/videos');
  const [maxUploadMB, setMaxUploadMB] = useState(500);
  const [pendingKind, setPendingKind] = useState<SourceKind>('file');
  const [pendingVideo, setPendingVideo] = useState<string | null>(null);
  const [pendingCamera, setPendingCamera] = useState<string | null>(null);
  const [pendingDevice, setPendingDevice] = useState<Device>(currentDevice);
  const [baslerCams, setBaslerCams] = useState<BaslerCamera[]>([]);
  const [baslerNote, setBaslerNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [uploadBusy, setUploadBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const refreshSources = useCallback(async () => {
    try {
      const [cfg, list, cams] = await Promise.all([
        api.getConfig(),
        api.listVideos(),
        api.listCameras().catch(() => ({ basler: [] } as { basler: BaslerCamera[]; basler_note?: string })),
      ]);
      setVideos(list.videos);
      setVideosDir(list.dir);
      setMaxUploadMB(list.max_upload_mb);
      setBaslerCams(cams.basler || []);
      setBaslerNote(cams.basler_note || null);

      const pending = api.getPendingSource();
      const runningKind = cfg.source?.kind === 'basler' ? 'basler' : 'file';
      const kind = pending?.kind === 'basler' ? 'basler' : pending?.kind === 'file' ? 'file' : runningKind;
      setPendingKind(kind);

      const pendingName = pending?.kind === 'file' ? pending.arg.replace(/^.*\//, '') : null;
      const runningName = cfg.video_file ? cfg.video_file.replace(/^.*\//, '') : null;
      setPendingVideo(pendingName ?? runningName ?? list.videos[0]?.name ?? null);

      const pendingSerial = pending?.kind === 'basler' ? pending.arg : null;
      setPendingCamera(pendingSerial ?? cams.basler?.[0]?.serial ?? null);
    } catch {
      setVideos([]);
      setBaslerCams([]);
      setPendingVideo(null);
      setPendingCamera(null);
    }
  }, []);

  useEffect(() => {
    setPendingDevice(currentDevice);
  }, [currentDevice]);

  useEffect(() => {
    refreshSources();
  }, [refreshSources]);

  const applyPendingSource = () => {
    if (pendingKind === 'file') {
      if (pendingVideo) {
        api.setPendingSource({ kind: 'file', arg: `${videosDir}/${pendingVideo}` });
      }
      return;
    }
    if (pendingCamera) {
      api.setPendingSource({ kind: 'basler', arg: pendingCamera });
    }
  };

  const handleStart = async () => {
    if (busy || isProcessing) return;
    setBusy(true);
    setStatus('Starting pipeline...');
    try {
      if (pendingDevice !== currentDevice) {
        await api.setDevice(pendingDevice);
        dispatch(setActiveDevice(pendingDevice));
      }
      applyPendingSource();
      dispatch(startProcessing());
      dispatch(startAllWorkloads());
      dispatch(patchDetectionState({ systemStatus: 'starting' }));
      const response = await api.start('all');
      if (response.status !== 'starting' && response.status !== 'running' && response.status !== 'ok') {
        throw new Error(`Start failed: ${JSON.stringify(response)}`);
      }
      dispatch({ type: 'sse/connect', payload: { url: api.getEventsUrl(['all']) } });
      setStatus('Pipeline started. Check the host display or terminal for the popup window.');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      dispatch(stopProcessing());
      dispatch(stopAllWorkloads());
      dispatch(patchDetectionState({ systemStatus: 'ready' }));
      setStatus(`Error: ${msg}`);
    } finally {
      setBusy(false);
    }
  };

  const handleStop = async () => {
    if (busy || !isProcessing) return;
    setBusy(true);
    setStatus('Stopping pipeline...');
    try {
      dispatch({ type: 'sse/disconnect' });
      dispatch(stopProcessing());
      dispatch(stopAllWorkloads());
      dispatch(patchDetectionState({ systemStatus: 'stopping' }));
      await api.stop('all');
      dispatch(patchDetectionState({ systemStatus: 'ready' }));
      setStatus('Pipeline stopped.');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      dispatch(patchDetectionState({ systemStatus: 'ready' }));
      setStatus(`Error: ${msg}`);
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    if (busy || isProcessing) return;
    setBusy(true);
    setStatus('Resetting session...');
    try {
      await api.reset();
      dispatch(resetDetectionState());
      dispatch(setActiveDevice(pendingDevice));
      setStatus('Session reset.');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`Error: ${msg}`);
    } finally {
      setBusy(false);
    }
  };

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setUploadBusy(true);
    setStatus('Uploading video...');
    try {
      const res = await api.uploadVideo(file);
      await refreshSources();
      setPendingKind('file');
      setPendingVideo(res.name);
      setStatus(`Uploaded ${res.name} (${formatMB(res.size_bytes)}).`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`Error: ${msg}`);
    } finally {
      setUploadBusy(false);
    }
  };

  return (
    <div className="config-panel">
      <details className="config-section" open>
        <summary>Source</summary>
        <div className="config-section-body">
          <label className="config-field">
            <span>Mode</span>
            <select value={pendingKind} onChange={(e) => setPendingKind(e.target.value as SourceKind)} disabled={busy || isProcessing}>
              <option value="file">Recorded file</option>
              <option value="basler">Basler live camera</option>
            </select>
          </label>

          {pendingKind === 'file' && (
            <>
              <label className="config-field">
                <span>Video file</span>
                <select value={pendingVideo ?? ''} onChange={(e) => setPendingVideo(e.target.value || null)} disabled={busy || isProcessing || videos.length === 0}>
                  {videos.length === 0 && <option value="">No videos available</option>}
                  {videos.map((video) => (
                    <option key={video.name} value={video.name}>{video.name}</option>
                  ))}
                </select>
              </label>
              <div className="config-actions-row">
                <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploadBusy || busy || isProcessing}>Upload video</button>
                <button type="button" onClick={refreshSources} disabled={uploadBusy || busy}>Refresh</button>
              </div>
              <p className="config-note">Max upload: {maxUploadMB} MB. Changes apply on next start.</p>
              <input ref={fileInputRef} type="file" accept="video/*" onChange={handleUpload} hidden />
            </>
          )}

          {pendingKind === 'basler' && (
            <>
              <label className="config-field">
                <span>Camera</span>
                <select value={pendingCamera ?? ''} onChange={(e) => setPendingCamera(e.target.value || null)} disabled={busy || isProcessing || baslerCams.length === 0}>
                  {baslerCams.length === 0 && <option value="">No Basler cameras detected</option>}
                  {baslerCams.map((camera) => (
                    <option key={camera.serial} value={camera.serial}>{camera.model} ({camera.serial})</option>
                  ))}
                </select>
              </label>
              <div className="config-actions-row">
                <button type="button" onClick={refreshSources} disabled={busy}>Refresh cameras</button>
              </div>
              <p className="config-note">Host must expose USB and X11 to the pipeline container.</p>
              {baslerNote && <p className="config-note">{baslerNote}</p>}
            </>
          )}
        </div>
      </details>

      <details className="config-section" open>
        <summary>Device</summary>
        <div className="config-section-body">
          <label className="config-field">
            <span>Inference device</span>
            <select value={pendingDevice} onChange={(e) => setPendingDevice(e.target.value as Device)} disabled={busy || isProcessing}>
              {DEVICE_OPTIONS.map((device) => (
                <option key={device} value={device}>{device}{device === currentDevice ? ' (current)' : ''}</option>
              ))}
            </select>
          </label>
          <p className="config-note">Device changes are applied the next time the pipeline starts.</p>
        </div>
      </details>

      <details className="config-section" open>
        <summary>Session</summary>
        <div className="config-section-body">
          <div className="config-actions-column">
            <button type="button" className="config-primary" onClick={handleStart} disabled={busy || isProcessing}>
              {busy && !isProcessing ? 'Starting...' : 'Start'}
            </button>
            <button type="button" onClick={handleStop} disabled={busy || !isProcessing}>
              {busy && isProcessing ? 'Stopping...' : 'Stop'}
            </button>
            <button type="button" onClick={handleReset} disabled={busy || isProcessing}>
              Reset session
            </button>
          </div>
          <p className="config-note">Live preview opens in a separate window on the host display. If it does not appear, check the terminal and X11 setup.</p>
          {status && <div className={`config-status${status.startsWith('Error') ? ' config-status-error' : ''}`}>{status}</div>}
        </div>
      </details>
    </div>
  );
};

export default ConfigPanel;