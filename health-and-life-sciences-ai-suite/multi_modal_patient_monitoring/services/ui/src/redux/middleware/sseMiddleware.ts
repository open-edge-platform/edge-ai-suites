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
        // Skip keepalive comments
        if (event.data.startsWith(':')) {
          return;
        }
      
        try {
          const data = JSON.parse(event.data);
          console.log('[SSE] 📨 Raw event:', data);
      
          // ✅ Extract workload_type (supports both 'workload_type' and 'workload')
          const workloadType = data.workload_type || data.workload;
          const eventType = data.event_type || 'data';
          const payload = data.payload || {};
          const timestamp = data.timestamp || Date.now();

          if (!workloadType) {
            console.warn('[SSE] ⚠️ Event missing workload_type:', data);
            return;
          }

          console.log(`[SSE] ✓ Processing ${workloadType} event:`, {
            eventType,
            payloadKeys: Object.keys(payload),
            hasWaveform: !!payload.waveform,
            timestamp
          });
      
          // ✅ Store raw event in eventsSlice
          store.dispatch(addEvent({
            id: `${workloadType}-${timestamp}-${Math.random().toString(36).substr(2, 9)}`,
            workload: workloadType,
            timestamp: timestamp,
            data: payload,
          }));
      
          // ✅ Parse data based on workload type
          let parsedData: any = {};
      
          if (workloadType === 'rppg') {
            // rPPG sends: HR, RR, SpO2, waveform
            parsedData = {
              HR: payload.HR ?? payload.heart_rate,
              RR: payload.RR ?? payload.respiratory_rate ?? payload.value,
              SpO2: payload.SpO2 ?? payload.spo2,
            };
            
            // Extract waveform if present
            if (payload.waveform && Array.isArray(payload.waveform)) {
              parsedData.waveform = payload.waveform;
            }
            
            console.log('[SSE] ✓ Parsed rPPG:', {
              vitals: { HR: parsedData.HR, RR: parsedData.RR, SpO2: parsedData.SpO2 },
              waveformLength: parsedData.waveform?.length
            });

          } else if (workloadType === 'ai-ecg') {
            console.log('[SSE] 🔬 AI-ECG raw payload:', JSON.stringify(payload, null, 2));
            
            // AI-ECG sends: inference object + waveform
            parsedData.prediction = payload.inference ?? 'Unknown';

            // ✅ Filename
            parsedData.filename = payload.file ?? 'Unknown';

            // ✅ Waveform
            if (Array.isArray(payload.waveform)) {
              parsedData.waveform = payload.waveform;
            }

            // ✅ Waveform frequency (very useful for ECG chart scaling)
            if (payload.waveform_frequency_hz) {
              parsedData.waveformFrequency = payload.waveform_frequency_hz;
            }
            
            console.log('[SSE] ✅ Final AI-ECG parsedData:', {
              prediction: parsedData.prediction,
              filename: parsedData.filename,
              waveformLength: parsedData.waveform?.length,
              allKeys: Object.keys(parsedData)
            });
          } else if (workloadType === 'mdpnp') {
            // MDPNP sends: device_type + metric + value/waveform
            console.log('[SSE] 🏥 MDPNP raw payload:', JSON.stringify(payload, null, 2));
            
            const eventType = data.event_type;
            const deviceType = data.device_type || payload.device_type;
            
            if (eventType === 'numeric') {
              // Map device metrics to unified vitals
              const metric = payload.metric;
              
              if (metric === 'MDC_ECG_HEART_RATE') {
                parsedData.HR = payload.value;
                console.log('[SSE] ✓ MDPNP HR:', payload.value);
              } 
              else if (metric === 'MDC_AWAY_CO2_ET') {
                parsedData.CO2_ET = payload.value;
                console.log('[SSE] ✓ MDPNP CO2_ET:', payload.value);
              } 
              else if (metric === 'MDC_PRESS_BLD_ART_ABP_DIA') {
                parsedData.BP_DIA = payload.value;
                console.log('[SSE] ✓ MDPNP BP_DIA:', payload.value);
              }
            } 
            else if (eventType === 'waveform') {
              // Extract waveform based on device type
              if (payload.waveform && Array.isArray(payload.waveform)) {
                // Store waveform with device identifier
                if (payload.metric === 'MDC_ECG_LEAD_II') {
                  parsedData.waveform = payload.waveform;
                  parsedData.waveformType = 'ECG';
                  console.log('[SSE] ✓ MDPNP ECG waveform:', payload.waveform.length, 'samples');
                } 
                else if (payload.metric === 'MDC_AWAY_CO2') {
                  parsedData.waveform = payload.waveform;
                  parsedData.waveformType = 'CO2';
                  console.log('[SSE] ✓ MDPNP CO2 waveform:', payload.waveform.length, 'samples');
                } 
                else if (payload.metric === 'MDC_PRESS_BLD') {
                  parsedData.waveform = payload.waveform;
                  parsedData.waveformType = 'BP';
                  console.log('[SSE] ✓ MDPNP BP waveform:', payload.waveform.length, 'samples');
                }
              }
            }
            
            console.log('[SSE] ✓ Parsed MDPNP:', {
              vitals: { HR: parsedData.HR, CO2_ET: parsedData.CO2_ET, BP_DIA: parsedData.BP_DIA },
              waveformType: parsedData.waveformType,
              waveformLength: parsedData.waveform?.length
            });
            
          } else if (workloadType === '3d-pose') {
            // 3D Pose sends: joints array + confidence + frame data
            parsedData = {
              joints: Array.isArray(payload.joints) 
                ? payload.joints.length 
                : (Array.isArray(payload.keypoints) ? payload.keypoints.length : 0),
              confidence: payload.confidence ?? 0,
              activity: payload.activity,
            };
          
            // ✅ Always include frame data immediately (no throttling)
            if (payload.frame_base64) {
              parsedData.frameData = `data:image/jpeg;base64,${payload.frame_base64}`;
              console.log(`[SSE] 🎬 Frame received for ${workloadType}`);
            }
            
            console.log('[SSE] ✓ Parsed 3D-Pose:', {
              ...parsedData,
              hasFrame: !!parsedData.frameData
            });
          } else {
            console.warn(`[SSE] ⚠️ Unknown workload type: ${workloadType}`);
          }

          // ✅ Dispatch for ALL workload types (moved outside the if-else chain)
          if (Object.keys(parsedData).length > 0) {
            store.dispatch(updateWorkloadData({
              workloadId: workloadType,
              payload: parsedData,
              timestamp,
            }));
          } else {
            console.warn(`[SSE] ⚠️ No data to dispatch for ${workloadType}`);
          }

        } catch (error) {
          console.error('[SSE] ❌ Error parsing event:', error);
        }
      }; // ✅ Missing closing brace for onmessage

      eventSource.onerror = (error) => {
        console.error('[SSE] ❌ Connection error:', error);
        store.dispatch(setAggregatorStatus('error'));
        
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }

        // ✅ Auto-reconnect after 5 seconds if still processing
        setTimeout(() => {
          const state = store.getState();
          if (state.app?.isProcessing) {
            console.log('[SSE] 🔄 Attempting reconnect...');
            store.dispatch({ type: 'sse/connect', payload: { url } });
          } else {
            console.log('[SSE] ⏹️ Not reconnecting - processing stopped');
          }
        }, 5000);
      };
    } // ✅ Missing closing brace for sse/connect action

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