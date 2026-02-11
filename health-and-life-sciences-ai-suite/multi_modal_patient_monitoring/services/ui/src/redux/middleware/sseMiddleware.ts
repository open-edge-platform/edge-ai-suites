import type { Middleware } from '@reduxjs/toolkit';
import { addEvent } from '../slices/eventsSlice';
import { updateWorkloadData, setAggregatorStatus } from '../slices/servicesSlice';

export const sseMiddleware: Middleware = (store) => {
  let eventSource: EventSource | null = null;

  return (next) => (action) => {
    if (typeof action !== 'object' || action === null || !('type' in action)) {
      return next(action);
    }

    // Handle SSE connect
    if (action.type === 'sse/connect') {
      const url = (action as any).payload?.url;
      
      if (!url) {
        console.error('[SSE] ❌ No URL provided');
        return next(action);
      }

      if (eventSource) {
        console.warn('[SSE] ⚠️ Already connected, closing existing connection');
        eventSource.close();
        eventSource = null;
      }

      console.log('[SSE] 🔌 Connecting to:', url);
      store.dispatch(setAggregatorStatus('connecting'));

      eventSource = new EventSource(url);

      eventSource.onopen = () => {
        console.log('[SSE] ✅ Connection established');
        store.dispatch(setAggregatorStatus('connected'));
      };

      eventSource.onmessage = (event) => {
        try {
          const rawData = JSON.parse(event.data);
          console.log('[SSE] 📨 Raw message:', rawData);

          const workloadType = rawData.workload_type || rawData.workload;
          const eventType = rawData.event_type || 'data';
          const payload = rawData.payload || rawData;
          const timestamp = rawData.timestamp || Date.now();

          // Parse workload-specific data
          let parsedData: any = {};

          if (workloadType === 'rppg') {
            parsedData = {
              HR: payload.HR || payload.hr,
              RR: payload.RR || payload.rr,
              waveform: payload.waveform || payload.respiratory_waveform,
            };
          } 
          else if (workloadType === 'ai-ecg') {
            parsedData = {
              prediction: payload.prediction,
              confidence: payload.confidence,
              filename: payload.filename,
              waveform: payload.waveform || payload.ecg_waveform,
            };
          } 
          else if (workloadType === 'mdpnp') {
            parsedData = {
              HR: payload.HR,
              SpO2: payload.SpO2,
              CO2_ET: payload.CO2_ET,
              BP_DIA: payload.BP_DIA,
              BP_SYS: payload.BP_SYS,
              waveform: payload.waveform,
            };
          } 
          else if (workloadType === '3d-pose') {
            let allPeopleJoints: any[] = [];
            
            console.log('[SSE] Raw 3D Pose payload:', payload);
            
            if (payload.people && Array.isArray(payload.people) && payload.people.length > 0) {
              // ✅ Extract joints from ALL people, not just the first one
              allPeopleJoints = payload.people.map((person: any) => {
                return {
                  person_id: person.person_id,
                  joints_3d: person.joints_3d || [],
                  confidence: person.confidence || [],
                };
              });
              
              console.log('[SSE] ✓ Extracted joints from all people:', {
                totalPeople: allPeopleJoints.length,
                jointsPerPerson: allPeopleJoints.map(p => p.joints_3d.length),
              });
            }
            
            parsedData = {
              activity: payload.activity || 'Unknown',
              people: allPeopleJoints,  // ✅ Send all people
              num_persons: payload.people?.length || 0,
              frame_number: payload.frame_number || 0,
            };

            console.log('[SSE] ✓ Dispatching to Redux:', parsedData);
          }

          // Dispatch to Redux
          store.dispatch(updateWorkloadData({
            workloadId: workloadType,
            data: parsedData,
            timestamp: timestamp
          }));

          // Also add to events log
          store.dispatch(addEvent({
            workload: workloadType,
            data: parsedData,
            timestamp: timestamp
          }));

        } catch (error) {
          console.error('[SSE] ❌ Parse error:', error);
        }
      };

      eventSource.onerror = (error) => {
        console.error('[SSE] ❌ Connection error:', error);
        store.dispatch(setAggregatorStatus('error'));
        
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }

        // Auto-reconnect after 5 seconds
        setTimeout(() => {
          const state = store.getState();
          if (state.app?.isProcessing) {
            console.log('[SSE] 🔄 Attempting reconnect...');
            store.dispatch({ type: 'sse/connect', payload: { url } });
          }
        }, 5000);
      };
    }

    // Handle SSE disconnect
    if (action.type === 'sse/disconnect') {
      console.log('[SSE] 🔌 Disconnecting...');
      
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      
      store.dispatch(setAggregatorStatus('stopped'));
    }

    return next(action);
  };
};