import { useEffect, useRef, useState } from 'react';
import { useAppSelector } from '../store';
import { api } from '../services/api';
import './VideoPanel.css';

/**
 * Live MJPEG view. Browsers stream multipart/x-mixed-replace into a single
 * <img> tag, which is why we don't need WebRTC or a JS decoder. The stream
 * URL is stable; we let nginx/backend keep the HTTP response open.
 */
export default function VideoPanel() {
  const lifecycle = useAppSelector((s) => s.status.lifecycle);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [streamError, setStreamError] = useState(false);

  // When lifecycle transitions to RUNNING, force a fresh <img> load.
  useEffect(() => {
    if (lifecycle === 'RUNNING' && imgRef.current) {
      imgRef.current.src = `${api.videoStreamUrl()}?t=${Date.now()}`;
      setStreamError(false);
    }
  }, [lifecycle]);

  const isLive = lifecycle === 'RUNNING';

  return (
    <section className="panel video-panel" aria-label="Live video">
      <div className="video-wrap">
        {isLive && !streamError ? (
          <img
            ref={imgRef}
            className="video-stream"
            src={api.videoStreamUrl()}
            alt="Live polyp detection overlay"
            onError={() => setStreamError(true)}
          />
        ) : (
          <div className="video-placeholder">
            <div className="video-placeholder-icon" aria-hidden>▶</div>
            <div className="video-placeholder-text">
              {streamError
                ? 'Stream unavailable — backend may be restarting'
                : lifecycle === 'STARTING'
                  ? 'Starting pipeline…'
                  : lifecycle === 'STOPPING'
                    ? 'Stopping…'
                    : 'Press Start to begin polyp detection'}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
