import React, { useEffect, useRef, useState } from 'react';
import type { NicuState } from '../../types/nicu';

interface VideoFeedProps {
  frameUrl: string | null;
  fps: number;
  systemStatus: NicuState['systemStatus'];
  polypDetected: boolean;
  polypCount: number;
  isExpanded?: boolean;
  panelExpanded?: boolean;
  onExpand?: () => void;
}

/**
 * Displays the live video feed from the backend by polling /frame/latest?base64=1.
 * Same base64-poll pattern as NICU to avoid MJPEG/React re-render races.
 */
const VideoFeed: React.FC<VideoFeedProps> = ({
  frameUrl,
  fps,
  systemStatus,
  polypDetected,
  polypCount,
}) => {
  const [frameSrc, setFrameSrc] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const cancelRef = useRef(false);
  const failCountRef = useRef(0);

  useEffect(() => {
    if (!frameUrl) {
      setFrameSrc(null);
      setStale(false);
      return;
    }

    cancelRef.current = false;
    failCountRef.current = 0;

    const baseUrl = frameUrl.replace(/\/video_feed$/, '');

    const poll = async () => {
      while (!cancelRef.current) {
        try {
          const res = await fetch(`${baseUrl}/frame/latest?base64=1`, { cache: 'no-store' });
          if (!cancelRef.current && res.ok) {
            const json = await res.json();
            if (!cancelRef.current && json.available && json.data) {
              setFrameSrc(`data:image/jpeg;base64,${json.data}`);
              setStale(false);
              failCountRef.current = 0;
            } else {
              failCountRef.current++;
            }
          } else {
            failCountRef.current++;
          }
        } catch {
          failCountRef.current++;
        }
        if (failCountRef.current >= 8 && !cancelRef.current) {
          setStale(true);
        }
        await new Promise((r) => setTimeout(r, 33));
      }
    };

    poll();
    return () => { cancelRef.current = true; };
  }, [frameUrl]);

  const statusClass =
    systemStatus === 'running'
      ? 'nicu-video-status--running'
      : systemStatus === 'error'
      ? 'nicu-video-status--error'
      : 'nicu-video-status--other';

  return (
    <div className="nicu-video">
      <div className={`nicu-video-status ${statusClass}`}>
        <span
          className={`nicu-video-status-dot ${
            systemStatus === 'running' || systemStatus === 'starting'
              ? 'nicu-video-status-dot--pulse'
              : ''
          }`}
        />
        {systemStatus.toUpperCase()}
      </div>

      <div className="nicu-video-overlays">
        <span className={`nicu-video-tag ${polypDetected ? '' : 'nicu-video-tag--off'}`}>
          Polyp: {polypDetected ? `Detected (${polypCount})` : 'Not Detected'}
        </span>
      </div>

      <span className="nicu-video-fps">{fps.toFixed(1)} FPS</span>

      {frameSrc ? (
        <div style={{ position: 'relative', width: '100%' }}>
          <img
            src={frameSrc}
            alt="Surgical Live Feed"
            style={{ display: 'block', width: '100%' }}
          />
          {stale && (
            <div style={{
              position: 'absolute', inset: 0,
              background: 'rgba(0,0,0,0.55)',
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              color: '#fff', gap: 8,
            }}>
              <div className="nicu-video-spinner" />
              <span style={{ fontSize: 13, fontWeight: 500 }}>Loading video feed…</span>
            </div>
          )}
        </div>
      ) : (
        <div className="nicu-video-placeholder">
          <span className="nicu-video-placeholder-icon">📹</span>
          <span className="nicu-video-placeholder-label">Polyp Detection Feed</span>
          <span className="nicu-video-placeholder-sub">
            Press Start to begin streaming detection overlays
          </span>
        </div>
      )}
    </div>
  );
};

export default VideoFeed;
