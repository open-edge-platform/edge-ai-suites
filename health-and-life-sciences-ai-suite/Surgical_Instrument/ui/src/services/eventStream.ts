/**
 * Server-Sent Events consumer.
 *
 * Backend emits two event types on /events:
 *   - "status"  → { lifecycle, message, ... }              (statusSlice)
 *   - "metrics" → { pipeline: {...}, system: {...} }       (metricsSlice)
 * Schema matches NICU-Warmer's /events so the consumer logic ports across.
 *
 * Auto-reconnects on transport error with a 1s back-off (capped at 10s).
 */

import type { AppDispatch } from '../store';
import { setStatus } from '../store/slices/statusSlice';
import { setPipelineMetrics, setSystemMetrics } from '../store/slices/metricsSlice';

export interface EventStreamHandle {
  close(): void;
}

export function openEventStream(dispatch: AppDispatch): EventStreamHandle {
  let es: EventSource | null = null;
  let retryMs = 1000;
  let stopped = false;
  let reconnectTimer: number | null = null;

  const connect = () => {
    if (stopped) return;
    es = new EventSource('/events');

    es.addEventListener('open', () => {
      retryMs = 1000;
    });

    es.addEventListener('status', (e) => {
      try {
        const payload = JSON.parse((e as MessageEvent).data);
        dispatch(setStatus(payload));
      } catch {
        /* ignore malformed */
      }
    });

    es.addEventListener('metrics', (e) => {
      try {
        const payload = JSON.parse((e as MessageEvent).data);
        if (payload.pipeline) dispatch(setPipelineMetrics(payload.pipeline));
        if (payload.system)   dispatch(setSystemMetrics(payload.system));
      } catch {
        /* ignore malformed */
      }
    });

    es.addEventListener('error', () => {
      es?.close();
      es = null;
      if (stopped) return;
      reconnectTimer = window.setTimeout(connect, retryMs);
      retryMs = Math.min(retryMs * 2, 10_000);
    });
  };

  connect();

  return {
    close() {
      stopped = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      es?.close();
    },
  };
}
