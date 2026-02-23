import type { Middleware } from '@reduxjs/toolkit';
import { addEvent } from '../slices/eventsSlice';
import { updateWorkloadData, setAggregatorStatus } from '../slices/servicesSlice';

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

      eventSource.onmessage = (event) => {
        try {
          const rawData = JSON.parse(event.data);
          
          const workloadType = rawData.workload_type || rawData.workload;
          const eventType = rawData.event_type || 'data';
          const payload = rawData.payload || rawData;
          const timestamp = rawData.timestamp || Date.now();

          // Parse workload-specific data
          let parsedData: any = {};

          if (workloadType === 'rppg') {
            // rPPG can send both waveform and numeric vitals
            if (eventType === 'numeric') {
              const metric = payload.metric;

              if (metric === 'HEART_RATE_AVG' || metric === 'HEART_RATE') {
                parsedData.HR = payload.value;
              } else if (metric === 'RESP_RATE_AVG' || metric === 'RESP_RATE') {
                parsedData.RR = payload.value;
              } else if (metric === 'SPO2' || metric === 'SPO2_AVG' || metric === 'OXYGEN_SATURATION') {
                parsedData.SpO2 = payload.value;
              }
            } else {
              // Waveform / aggregated payload
              parsedData = {
                HR: payload.HR ?? payload.heart_rate,
                RR: payload.RR ?? payload.respiratory_rate ?? payload.value,
                SpO2: payload.SpO2 ?? payload.spo2,
              };
              
              // Extract waveform if present
              if (payload.waveform && Array.isArray(payload.waveform)) {
                parsedData.waveform = payload.waveform;
              }
            }

          } else if (workloadType === 'ai-ecg') {
            // AI-ECG sends: inference object + waveform
            parsedData.prediction = payload.inference ?? 'Unknown';
            parsedData.filename = payload.file ?? 'Unknown';

            // Waveform
            if (Array.isArray(payload.waveform)) {
              parsedData.waveform = payload.waveform;
            }

            // Waveform frequency (very useful for ECG chart scaling)
            if (payload.waveform_frequency_hz) {
              parsedData.waveformFrequency = payload.waveform_frequency_hz;
            }
            
          } else if (workloadType === 'mdpnp') {
            // MDPNP sends: device_type + metric + value/waveform
            const eventType = rawData.event_type;
            const deviceType = rawData.device_type || payload.device_type;
            
            if (eventType === 'numeric') {
              // Map device metrics to unified vitals
              const metric = payload.metric;
              
              if (metric === 'MDC_ECG_HEART_RATE') {
                parsedData.HR = payload.value;
              } 
              else if (metric === 'MDC_AWAY_CO2_ET') {
                parsedData.CO2_ET = payload.value;
              } 
              else if (metric === 'MDC_PRESS_BLD_ART_ABP_DIA') {
                parsedData.BP_DIA = payload.value;
              }
              else if (metric === 'MDC_PRESS_BLD_ART_ABP_SYS') {
                parsedData.BP_SYS = payload.value;
              }
            } 
            else if (eventType === 'waveform') {
              // Extract waveform based on device type
              if (payload.waveform && Array.isArray(payload.waveform)) {
                // Store waveform with device identifier
                if (payload.metric === 'MDC_ECG_LEAD_II') {
                  parsedData.waveform = payload.waveform;
                  parsedData.waveformType = 'ECG';
                } 
                else if (payload.metric === 'MDC_AWAY_CO2') {
                  parsedData.waveform = payload.waveform;
                  parsedData.waveformType = 'CO2';
                } 
                else if (payload.metric === 'MDC_PRESS_BLD') {
                  parsedData.waveform = payload.waveform;
                  parsedData.waveformType = 'BP';
                }
              }
            }
            
          } else if (workloadType === '3d-pose') {
            poseMessageCount++;
            
            let allPeopleJoints: any[] = [];
            
            if (payload.people && Array.isArray(payload.people) && payload.people.length > 0) {
              // Extract joints from ALL people, not just the first one
              allPeopleJoints = payload.people.map((person: any) => {
                return {
                  person_id: person.person_id,
                  joints_3d: person.joints_3d || [],
                  confidence: person.confidence || [],
                };
              });
            }
            
            parsedData = {
              activity: payload.activity || 'Unknown',
              people: allPeopleJoints,
              num_persons: payload.people?.length || 0,
              frame_number: payload.frame_number || 0,
            };

            // Always include frame data immediately (no throttling)
            if (payload.frame_base64) {
              parsedData.frameData = `data:image/jpeg;base64,${payload.frame_base64}`;
            }
            
          }

          const state: any = store.getState();
          const isProcessing = state.app?.isProcessing;
          if (!isProcessing) {
            return;
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
            timestamp: timestamp,
            id: ''
          }));

        } catch (error) {
          // Silent error handling
        }
      };

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
    }

    return next(action);
  };
};