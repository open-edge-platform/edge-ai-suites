import { useEffect, useState } from 'react';
import { useAppSelector } from '../../redux/hooks';
import { api } from '../../services/api';
import '../../assets/css/TopPanel.css';

const TopPanel = () => {
  const systemStatus = useAppSelector((state) => state.detection.data.systemStatus);
  const [notification, setNotification] = useState<string>('');
  const [isBackendReady, setIsBackendReady] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const ok = await api.pingBackend();
        if (!cancelled) setIsBackendReady(ok);
      } catch {
        if (!cancelled) setIsBackendReady(false);
      }
    };
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

  return (
    <div className="top-panel">
      <div className="action-buttons">
        <span className="start-button" style={{ opacity: 1, cursor: 'default' }}>
          {isBackendReady ? 'Backend ready' : 'Backend offline'}
        </span>
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
        <span className="settings-button-label">Configure source, device, and session from the left panel.</span>
      </div>
    </div>
  );
};

export default TopPanel;
