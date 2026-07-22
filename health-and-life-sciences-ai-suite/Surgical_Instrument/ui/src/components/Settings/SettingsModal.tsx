import React from 'react';

const SettingsModal: React.FC = () => null;

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
