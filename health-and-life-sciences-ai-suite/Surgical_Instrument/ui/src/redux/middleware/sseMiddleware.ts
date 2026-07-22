import type { Middleware } from '@reduxjs/toolkit';
import { addEvent } from '../slices/eventsSlice';
import { updateWorkloadData, setAggregatorStatus } from '../slices/servicesSlice';
import { patchDetectionState } from '../slices/detectionSlice';
import { api } from '../../services/api';

/**
 * SSE middleware for the surgical-instrument backend.
 *
 * Listens for two named events from /api/events:
 *   - "full"  : initial / periodic full snapshot
 *   - "delta" : changed-fields-only patch
 *
 * Payload shape:
 *   {
 *     lifecycle?: 'starting' | 'running' | 'stopping' | 'error',
 *     analytics?: { polyp_detection?: { detected, count, confidence } },
 *     metrics?:   { fps, loop_count },
 *     pipeline_performance?: { workloads: [...], pipeline_fps, decode },
 *     frame?:     true,  // when present, signals there's a fresh frame at /frame/latest
 *   }
 */
export const sseMiddleware: Middleware = (store) => {
  let eventSource: EventSource | null = null;

  return (next) => (action: any) => {
    if (typeof action !== 'object' || action === null || !('type' in action)) {
      return next(action);
    }

    if (action.type === 'sse/connect') {
      const url = action.payload?.url;
      if (!url) return next(action);

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
          if (payload.analytics?.polyp_detection !== undefined) {
            const p = payload.analytics.polyp_detection;
            detectionPatch.polyp = {
              detected: !!p.detected,
              count: p.count ?? 0,
              confidence: p.confidence ?? 0,
              distinct_polyps: p.distinct_polyps ?? 0,
              frames_processed: p.frames_processed ?? 0,
              frames_with_detection: p.frames_with_detection ?? 0,
              detection_rate: p.detection_rate ?? 0,
              peak_confidence: p.peak_confidence ?? 0,
              session_seconds: p.session_seconds ?? 0,
            };
          }
          if (payload.frame !== undefined) {
            detectionPatch.frameUrl = api.getFrameUrl();
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
          if (payload.pipeline_performance !== undefined) {
            const workloads = (payload.pipeline_performance.workloads ?? []).map((w: any) => ({
              ...w,
              fps: w?.fps ?? 0,
              infer_ms: w?.infer_ms ?? 0,
              infer_p50_ms: w?.infer_p50_ms ?? 0,
              infer_p90_ms: w?.infer_p90_ms ?? 0,
              infer_p95_ms: w?.infer_p95_ms ?? 0,
              infer_p99_ms: w?.infer_p99_ms ?? 0,
              processing_mean_ms: w?.processing_mean_ms ?? 0,
              processing_p50_ms: w?.processing_p50_ms ?? 0,
              processing_p90_ms: w?.processing_p90_ms ?? 0,
              processing_p95_ms: w?.processing_p95_ms ?? 0,
              processing_p99_ms: w?.processing_p99_ms ?? 0,
              e2e_mean_ms: w?.e2e_mean_ms ?? 0,
              e2e_p50_ms: w?.e2e_p50_ms ?? 0,
              e2e_p90_ms: w?.e2e_p90_ms ?? 0,
              e2e_p95_ms: w?.e2e_p95_ms ?? 0,
              e2e_p99_ms: w?.e2e_p99_ms ?? 0,
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

          store.dispatch(updateWorkloadData({
            workloadId: 'polyp',
            data: payload?.analytics?.polyp_detection ?? {},
            timestamp,
          }));

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
        store.dispatch(setAggregatorStatus('error'));
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
        setTimeout(() => {
          const state: any = store.getState();
          if (state.app?.isProcessing) {
            store.dispatch({ type: 'sse/connect', payload: { url } });
          }
        }, 5000);
      };
    }

    if (action.type === 'sse/disconnect') {
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
