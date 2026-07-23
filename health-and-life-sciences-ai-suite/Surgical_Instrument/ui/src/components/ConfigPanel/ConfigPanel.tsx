import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAppSelector } from '../../redux/hooks';
import { api, type BaslerCamera, type Device, type VideoItem } from '../../services/api';
import '../../assets/css/ConfigPanel.css';

type SourceKind = 'file' | 'basler';

const formatMB = (n: number) => `${(n / (1024 * 1024)).toFixed(1)} MB`;

const ConfigPanel: React.FC = () => {
  const systemStatus = useAppSelector((state) => state.detection.data.systemStatus);
  const modelInfo = useAppSelector((state) => state.detection.data.modelInfo);
  const pipelinePerf = useAppSelector((state) => state.detection.data.pipelinePerformance);

  const isProcessing = systemStatus === 'running' || systemStatus === 'starting';
  const currentDevice = useMemo<Device>(
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
  const [status, setStatus] = useState('');
  const [uploadBusy, setUploadBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const hasBasler = baslerCams.length > 0;

  const DEVICE_OPTIONS: Device[] = ['GPU', 'CPU', 'NPU'];

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
      const requestedKind = pending?.kind === 'basler' ? 'basler' : pending?.kind === 'file' ? 'file' : runningKind;
      const hasDetectedBasler = (cams.basler || []).length > 0;
      const kind = requestedKind === 'basler' && !hasDetectedBasler ? 'file' : requestedKind;
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
    refreshSources();
  }, [refreshSources]);

  useEffect(() => {
    setPendingDevice(currentDevice);
  }, [currentDevice]);

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
      console.error('Upload failed', err);
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`Error: ${msg}`);
    } finally {
      setUploadBusy(false);
    }
  };

  useEffect(() => {
    if (isProcessing) return;
    applyPendingSource();
  }, [pendingKind, pendingVideo, pendingCamera, isProcessing, videosDir]);

  useEffect(() => {
    if (isProcessing || hasBasler || pendingKind !== 'basler') return;
    setPendingKind('file');
    setStatus('No Basler camera detected. Using recorded file source.');
  }, [pendingKind, hasBasler, isProcessing]);

  useEffect(() => {
    api.setPendingDevice(pendingDevice);
  }, [pendingDevice]);

  return (
    <div className="config-panel">
      <details className="config-section" open>
        <summary>Source</summary>
        <div className="config-section-body">
          <label className="config-field">
            <span>Mode</span>
            <select value={pendingKind} onChange={(e) => setPendingKind(e.target.value as SourceKind)} disabled={isProcessing}>
              <option value="file">Recorded file</option>
              {hasBasler && <option value="basler">Basler live camera</option>}
            </select>
          </label>
          {!hasBasler && <p className="config-note">No Basler camera detected. Live camera mode is unavailable.</p>}

          {pendingKind === 'file' && (
            <>
              <label className="config-field">
                <span>Video file</span>
                <select value={pendingVideo ?? ''} onChange={(e) => setPendingVideo(e.target.value || null)} disabled={isProcessing || videos.length === 0}>
                  {videos.length === 0 && <option value="">No videos available</option>}
                  {videos.map((video) => (
                    <option key={video.name} value={video.name}>{video.name}</option>
                  ))}
                </select>
              </label>
              <div className="config-actions-row">
                <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploadBusy || isProcessing}>Upload video</button>
                <button type="button" onClick={refreshSources} disabled={uploadBusy}>Refresh</button>
              </div>
              <p className="config-note">Max upload: {maxUploadMB} MB. Changes apply on next start.</p>
              <input ref={fileInputRef} type="file" accept="video/*" onChange={handleUpload} hidden />
            </>
          )}

          {pendingKind === 'basler' && (
            <>
              <label className="config-field">
                <span>Camera</span>
                <select value={pendingCamera ?? ''} onChange={(e) => setPendingCamera(e.target.value || null)} disabled={isProcessing || baslerCams.length === 0}>
                  {baslerCams.length === 0 && <option value="">No Basler cameras detected</option>}
                  {baslerCams.map((camera) => (
                    <option key={camera.serial} value={camera.serial}>{camera.model} ({camera.serial})</option>
                  ))}
                </select>
              </label>
              <div className="config-actions-row">
                <button type="button" onClick={refreshSources}>Refresh cameras</button>
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
            <select value={pendingDevice} onChange={(e) => setPendingDevice(e.target.value as Device)} disabled={isProcessing}>
              {DEVICE_OPTIONS.map((device) => (
                <option key={device} value={device}>{device}{device === currentDevice ? ' (current)' : ''}</option>
              ))}
            </select>
          </label>
          <p className="config-note">Device changes are applied the next time the pipeline starts.</p>
        </div>
      </details>

      {status && <div className={`config-status${status.startsWith('Error') ? ' config-status-error' : ''}`}>{status}</div>}
    </div>
  );
};

export default ConfigPanel;