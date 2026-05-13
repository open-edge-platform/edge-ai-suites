import type { Middleware } from '@reduxjs/toolkit';
import { addEvent } from '../slices/eventsSlice';
import { updateWorkloadData, setAggregatorStatus } from '../slices/servicesSlice';
import { patchNicuState, resetNicuState } from '../slices/nicuSlice';

import { api } from '../../services/api';

function mapLatch(raw: string | undefined): 'open' | 'closed' | 'unknown' {
  const v = (raw || '').toLowerCase();
  if (v === 'closed') return 'closed';
  if (v === 'open') return 'open';
  return 'unknown';
}

export const sseMiddleware: Middleware = (store) => {
  let eventSource: EventSource | null = null;
  let poseMessageCount = 0;

  return (next) => (action) => {
    if (typeof action !== 'object' || action === null || !('type' in action)) {
      return next(action);
    }

    // Handle SSE connect
    if (action.type === 'sse/connect') {
      const url = (action as any).payload?.url;
      
      if (!url) {
        return next(action);
      }

      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }

      store.dispatch(setAggregatorStatus('connecting'));

      eventSource = new EventSource(url);

      eventSource.onopen = () => {
        store.dispatch(setAggregatorStatus('connected'));
      };

      // Backend sends named events ("full" and "delta"), not unnamed ones.
      // We handle both identically: parse JSON and patch the NICU state.
      const handleSSEData = (event: MessageEvent) => {
        try {
          const rawData = JSON.parse(event.data);
          const payload = rawData;
          const timestamp = Date.now();

          // Only include fields that are actually present in the payload.
          // Delta events carry only changed fields; we must not overwrite
          // existing state with defaults for missing fields.
          const nicuPatch: any = {};

          if (payload.lifecycle !== undefined) {
            nicuPatch.systemStatus = payload.lifecycle;
          }
          if (payload.analytics !== undefined) {
            const a = payload.analytics;
            if (a.patient_presence !== undefined) {
              nicuPatch.patient = {
                detected: !!a.patient_presence,
                confidence: null,
              };
            }
            if (a.caretaker_presence !== undefined) {
              nicuPatch.caretaker = {
                detected: !!a.caretaker_presence,
                count: a.caretaker_presence ? 1 : 0,
                confidence: null,
              };
            }
            if (a.latch_status !== undefined) {
              nicuPatch.latch = {
                state: mapLatch(a.latch_status),
                confidence: null,
              };
            }
            if (a.action !== undefined) {
              nicuPatch.action = {
                activities: a.action.activities ?? [],
                top_activity: a.action.top_activity ?? 'Unknown',
                top_confidence: a.action.top_confidence ?? 0,
                status: a.action.status ?? 'warming_up',
                motion_level: a.action.motion_level,
                motion_magnitude: a.action.motion_magnitude,
              };
            }
          }
          if (payload.rppg !== undefined) {
            const r = payload.rppg;
            const prevRppg = (store.getState() as any).nicu?.data?.rppg;
            nicuPatch.rppg = { ...prevRppg };
            if ('heart_rate_bpm' in r)      nicuPatch.rppg.heartRate = r.heart_rate_bpm ?? prevRppg?.heartRate ?? null;
            if ('respiration_rate_bpm' in r) nicuPatch.rppg.respirationRate = r.respiration_rate_bpm ?? prevRppg?.respirationRate ?? null;
            if ('signal_confidence' in r)    nicuPatch.rppg.confidence = r.signal_confidence ?? 0;
            if ('pulse_waveform' in r)       nicuPatch.rppg.waveform = r.pulse_waveform ?? [];
            if ('resp_waveform' in r)        nicuPatch.rppg.respWaveform = r.resp_waveform ?? [];
          }
          if (payload.frame !== undefined) {
            nicuPatch.frameUrl = api.getFrameUrl();
          }
          if (payload.metrics !== undefined) {
            nicuPatch.fps = payload.metrics.fps ?? 0;
            nicuPatch.uptime = payload.metrics.loop_count ?? 0;
          }
          if (payload.pipeline_performance !== undefined) {
            nicuPatch.pipelinePerformance = {
              workloads: payload.pipeline_performance.workloads ?? [],
              pipeline_fps: payload.pipeline_performance.pipeline_fps ?? 0,
              decode: payload.pipeline_performance.decode ?? '',
            };
          }

          store.dispatch(patchNicuState(nicuPatch));

          const state: any = store.getState();
          const isProcessing = state.app?.isProcessing;

          // Keep the existing event log/state for compatibility while
          // NICU-specific components migrate fully to nicuSlice.
          store.dispatch(updateWorkloadData({
            workloadId: 'rppg',
            data: {
              HR: payload?.rppg?.heart_rate_bpm,
              RR: payload?.rppg?.respiration_rate_bpm,
            },
            timestamp: timestamp,
          }));

          // Also add to events log
          store.dispatch(addEvent({
            workload: 'rppg',
            data: payload,
            timestamp: timestamp,
            id: ''
          }));

        } catch (error) {
          // Silent error handling
        }
      };

      // Listen for named events from backend SSE
      eventSource.addEventListener('full', handleSSEData);
      eventSource.addEventListener('delta', handleSSEData);
      // Also handle unnamed events as fallback
      eventSource.onmessage = handleSSEData;

      eventSource.onerror = (error) => {
        store.dispatch(setAggregatorStatus('error'));
        
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }

        // Auto-reconnect after 5 seconds
        setTimeout(() => {
          const state = store.getState();
          if (state.app?.isProcessing) {
            store.dispatch({ type: 'sse/connect', payload: { url } });
          }
        }, 5000);
      };
    }

    // Handle SSE disconnect
    if (action.type === 'sse/disconnect') {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      
      store.dispatch(setAggregatorStatus('stopped'));
      // Reset NICU state but preserve metrics so charts freeze with last data
      store.dispatch(resetNicuState());
    }

    return next(action);
  };
};