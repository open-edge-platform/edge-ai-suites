import { useEffect, useState } from 'react';
import { useAppSelector } from '../../redux/hooks';
import { useAppDispatch } from '../../redux/hooks';
import { startProcessing, stopProcessing } from '../../redux/slices/appSlice';
import { startAllWorkloads, stopAllWorkloads } from '../../redux/slices/servicesSlice';
import { patchDetectionState, resetDetectionState, setActiveDevice } from '../../redux/slices/detectionSlice';
import { api } from '../../services/api';
import '../../assets/css/TopPanel.css';

type UiLifecycle = 'initializing' | 'preparing' | 'ready' | 'starting' | 'running' | 'error' | 'stopping';

const normalizeLifecycle = (value: string): UiLifecycle => {
  const v = value.toLowerCase();
  if (v === 'initializing' || v === 'preparing' || v === 'ready' || v === 'starting' || v === 'running' || v === 'error' || v === 'stopping') {
    return v;
  }
  return 'ready';
};

const TopPanel = () => {
  const dispatch = useAppDispatch();
  const systemStatus = useAppSelector((state) => state.detection.data.systemStatus);
  const [notification, setNotification] = useState<string>('');
  const [isBackendReady, setIsBackendReady] = useState(true);
  const [busy, setBusy] = useState(false);
  const [showInfo, setShowInfo] = useState(false);

  const isProcessing = systemStatus === 'running' || systemStatus === 'starting';

  const attachRunningSession = (lifecycle: UiLifecycle) => {
    dispatch(startProcessing());
    dispatch(startAllWorkloads());
    dispatch(patchDetectionState({ systemStatus: lifecycle }));
    dispatch({ type: 'sse/connect', payload: { url: api.getEventsUrl(['all']) } });
    setShowInfo(true);
  };

  useEffect(() => {
    let cancelled = false;
    const hydrateRuntimeState = async () => {
      try {
        let snap = await api.getStatusSnapshot();
        let lifecycle = normalizeLifecycle(String(snap?.lifecycle || 'ready'));
        const inf = snap?.inference;

        // Recover a stale backend state where lifecycle says running but
        // the pipeline process is no longer active.
        if ((lifecycle === 'running' || lifecycle === 'starting') && inf && inf.pipeline_running === false) {
          try {
            await api.stop('all');
          } catch {
            // Ignore stop race/errors and re-read status below.
          }
          snap = await api.getStatusSnapshot();
          lifecycle = normalizeLifecycle(String(snap?.lifecycle || 'ready'));
        }

        if (cancelled) return;
        if (lifecycle === 'running' || lifecycle === 'starting') {
          attachRunningSession(lifecycle);
        } else {
          dispatch(stopProcessing());
          dispatch(stopAllWorkloads());
          dispatch(patchDetectionState({ systemStatus: lifecycle }));
        }
      } catch {
        // Best-effort hydration only.
      }
    };

    const check = async () => {
      try {
        const ok = await api.pingBackend();
        if (!cancelled) setIsBackendReady(ok);
      } catch {
        if (!cancelled) setIsBackendReady(false);
      }
    };
    hydrateRuntimeState();
    check();
    const id = setInterval(check, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  useEffect(() => {
    if (!isBackendReady) {
      setNotification('Backend offline');
      return;
    }
    setNotification(`Status: ${systemStatus}`);
  }, [isBackendReady, systemStatus]);

  const handleStart = async () => {
    if (busy || isProcessing || !isBackendReady) return;
    setShowInfo(true);
    setBusy(true);
    setNotification('Starting pipeline...');
    try {
      const snap = await api.getStatusSnapshot();
      const lifecycle = normalizeLifecycle(String(snap?.lifecycle || 'ready'));
      const inf = snap?.inference;

      // If backend is already running, just reconnect UI stream.
      if ((lifecycle === 'running' || lifecycle === 'starting') && inf?.pipeline_running !== false) {
        attachRunningSession(lifecycle);
        setNotification('Pipeline already running. Reconnected to live stream.');
        return;
      }

      // If lifecycle is stale-running with dead pipeline, clear it first.
      if ((lifecycle === 'running' || lifecycle === 'starting') && inf?.pipeline_running === false) {
        try {
          await api.stop('all');
        } catch {
          // continue and let start try; backend may already be transitioning.
        }
      }

      const pendingDevice = api.getPendingDevice();
      if (pendingDevice) {
        await api.setDevice(pendingDevice);
        dispatch(setActiveDevice(pendingDevice));
      }
      dispatch(startProcessing());
      dispatch(startAllWorkloads());
      dispatch(patchDetectionState({ systemStatus: 'starting' }));
      const response = await api.start('all');
      if (response.status !== 'starting' && response.status !== 'running' && response.status !== 'ok') {
        throw new Error(`Start failed: ${JSON.stringify(response)}`);
      }
      dispatch({ type: 'sse/connect', payload: { url: api.getEventsUrl(['all']) } });
      setNotification('Pipeline started.');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);

      // Common stale-UI case: backend is already running and rejects /device.
      if (msg.toLowerCase().includes('cannot change device while running')) {
        attachRunningSession('running');
        setNotification('Pipeline already running. Reconnected to live stream.');
        return;
      }

      dispatch(stopProcessing());
      dispatch(stopAllWorkloads());
      dispatch(patchDetectionState({ systemStatus: 'ready' }));
      setNotification(`Error: ${msg}`);
    } finally {
      setBusy(false);
    }
  };

  const handleStop = async () => {
    if (busy || !isProcessing || !isBackendReady) return;
    setBusy(true);
    setNotification('Stopping pipeline...');
    try {
      dispatch({ type: 'sse/disconnect' });
      dispatch(stopProcessing());
      dispatch(stopAllWorkloads());
      dispatch(patchDetectionState({ systemStatus: 'stopping' }));
      await api.stop('all');
      dispatch(patchDetectionState({ systemStatus: 'ready' }));
      setNotification('Pipeline stopped.');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      dispatch(patchDetectionState({ systemStatus: 'ready' }));
      setNotification(`Error: ${msg}`);
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    if (busy || isProcessing || !isBackendReady) return;
    setBusy(true);
    setNotification('Resetting session...');
    try {
      await api.reset();
      dispatch(resetDetectionState());
      setNotification('Session reset.');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setNotification(`Error: ${msg}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="top-panel">
      <div className="action-buttons">
        <button type="button" className="start-button" onClick={handleStart} disabled={busy || isProcessing || !isBackendReady}>
          {busy && !isProcessing ? 'Starting...' : 'Start'}
        </button>
        <button type="button" className="stop-button" onClick={handleStop} disabled={busy || !isProcessing || !isBackendReady}>
          {busy && isProcessing ? 'Stopping...' : 'Stop'}
        </button>
        <button type="button" className="reset-button" onClick={handleReset} disabled={busy || isProcessing || !isBackendReady}>
          Reset session
        </button>
      </div>

      <div className="notification-center">
        {notification && (
          <span style={{
            padding: '8px 16px',
            background: isBackendReady ? '#efe' : '#fee',
            borderRadius: '4px',
            fontSize: '13px',
            border: `1px solid ${isBackendReady ? '#cfc' : '#fcc'}`,
          }}>
            {notification}
          </span>
        )}
      </div>

      <div className="top-panel-right">
        {showInfo && (
          <span className="settings-button-label">Live preview opens in a separate window on the host display.</span>
        )}
      </div>
    </div>
  );
};

export default TopPanel;
