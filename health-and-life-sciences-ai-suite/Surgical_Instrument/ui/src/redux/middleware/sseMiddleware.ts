import type { Middleware } from '@reduxjs/toolkit';
import { addEvent } from '../slices/eventsSlice';
import { updateWorkloadData, setAggregatorStatus } from '../slices/servicesSlice';
import { patchDetectionState } from '../slices/detectionSlice';

/**
 * SSE middleware for the surgical-instrument backend.
 *
 * Listens for two named events from /api/events:
 *   - "full"  : initial / periodic full snapshot
 *   - "delta" : changed-fields-only patch
 *
 * Payload shape:
 *   { lifecycle?, metrics?, pipeline_latency?, pipeline_performance?, model_info? }
 */
export const sseMiddleware: Middleware = (store) => {
  let eventSource: EventSource | null = null;
  let reconnectTimer: number | null = null;
  let connectionToken = 0;

  const clearReconnectTimer = () => {
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  return (next) => (action: any) => {
    if (typeof action !== 'object' || action === null || !('type' in action)) {
      return next(action);
    }

    if (action.type === 'sse/connect') {
      const url = action.payload?.url;
      if (!url) return next(action);
      connectionToken += 1;
      const activeToken = connectionToken;
      clearReconnectTimer();

      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }

      store.dispatch(setAggregatorStatus('connecting'));

      eventSource = new EventSource(url);

      eventSource.onopen = () => store.dispatch(setAggregatorStatus('connected'));

      const handleSSEData = (event: MessageEvent) => {
        try {
          const payload = JSON.parse(event.data);
          const timestamp = Date.now();
          const detectionPatch: any = {};

          if (payload.lifecycle !== undefined) {
            detectionPatch.systemStatus = payload.lifecycle;
          }
          if (payload.metrics !== undefined) {
            detectionPatch.fps = payload.metrics.fps ?? 0;
            detectionPatch.totalFrames = payload.metrics.loop_count ?? 0;
            detectionPatch.uptime = payload.metrics.uptime_s ?? 0;
            detectionPatch.inferP50Ms = payload.metrics.infer_p50_ms ?? 0;
            detectionPatch.inferP90Ms = payload.metrics.infer_p90_ms ?? 0;
            detectionPatch.inferP95Ms = payload.metrics.infer_p95_ms ?? 0;
            detectionPatch.inferP99Ms = payload.metrics.infer_p99_ms ?? 0;
            detectionPatch.totalP50Ms = payload.metrics.e2e_p50_ms ?? 0;
            detectionPatch.totalP90Ms = payload.metrics.e2e_p90_ms ?? 0;
            detectionPatch.totalP95Ms = payload.metrics.e2e_p95_ms ?? 0;
            detectionPatch.totalP99Ms = payload.metrics.total_p99_ms ?? 0;
          }
          if (payload.pipeline_latency !== undefined) {
            detectionPatch.pipelineLatency = {
              mean_ms: payload.pipeline_latency.mean_ms ?? 0,
              p50_ms: payload.pipeline_latency.p50_ms ?? 0,
              p90_ms: payload.pipeline_latency.p90_ms ?? 0,
              p95_ms: payload.pipeline_latency.p95_ms ?? 0,
              p99_ms: payload.pipeline_latency.p99_ms ?? 0,
            };
          }
          if (payload.pipeline_performance !== undefined) {
            const workloads = (payload.pipeline_performance.workloads ?? []).map((w: any) => ({
              ...w,
              fps: w?.fps ?? 0,
              processing_mean_ms: w?.processing_mean_ms ?? 0,
              processing_p50_ms: w?.processing_p50_ms ?? 0,
              processing_p90_ms: w?.processing_p90_ms ?? 0,
              processing_p95_ms: w?.processing_p95_ms ?? 0,
              processing_p99_ms: w?.processing_p99_ms ?? 0,
              latency_ms: w?.latency_ms ?? 0,
              latency_p99_ms: w?.latency_p99_ms ?? 0,
            }));
            detectionPatch.pipelinePerformance = {
              workloads,
              pipeline_fps: payload.pipeline_performance.pipeline_fps ?? 0,
              decode: payload.pipeline_performance.decode ?? '',
            };
          }
          if (payload.model_info !== undefined) {
            detectionPatch.modelInfo = payload.model_info;
          }

          store.dispatch(patchDetectionState(detectionPatch));

          store.dispatch(updateWorkloadData({ workloadId: 'polyp', data: {}, timestamp }));

          store.dispatch(addEvent({
            workload: 'polyp',
            data: payload,
            timestamp,
            id: '',
          }));
        } catch {
          /* ignore malformed events */
        }
      };

      eventSource.addEventListener('full', handleSSEData);
      eventSource.addEventListener('delta', handleSSEData);
      eventSource.onmessage = handleSSEData;

      eventSource.onerror = () => {
        if (activeToken !== connectionToken) {
          return;
        }
        store.dispatch(setAggregatorStatus('error'));
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
        reconnectTimer = window.setTimeout(() => {
          if (activeToken !== connectionToken) {
            return;
          }
          const state: any = store.getState();
          if (state.app?.isProcessing) {
            store.dispatch({ type: 'sse/connect', payload: { url } });
          }
        }, 5000);
      };
    }

    if (action.type === 'sse/disconnect') {
      connectionToken += 1;
      clearReconnectTimer();
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      store.dispatch(setAggregatorStatus('stopped'));
      // Deliberately do NOT reset detection state — freeze the last snapshot
      // (video, KPIs, session totals) so the user can review the final session
      // after clicking Stop. On next Start the backend clears the frozen snapshot.
    }

    return next(action);
  };
};
