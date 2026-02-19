import type { Middleware } from '@reduxjs/toolkit';
import { addEvent } from '../slices/eventsSlice';
import { updateWorkloadData, setAggregatorStatus } from '../slices/servicesSlice';

export const sseMiddleware: Middleware = (store) => {
  let eventSource: EventSource | null = null;
  let poseMessageCount = 0; // ✅ Add counter for 3D Pose messages

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

              console.log('[SSE] ✓ Parsed rPPG numeric:', {
                metric,
                value: payload.value,
                vitals: { HR: parsedData.HR, RR: parsedData.RR, SpO2: parsedData.SpO2 },
              });
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
              
              console.log('[SSE] ✓ Parsed rPPG (waveform/aggregate):', {
                vitals: { HR: parsedData.HR, RR: parsedData.RR, SpO2: parsedData.SpO2 },
                waveformLength: parsedData.waveform?.length
              });
            }

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
            
            const eventType = rawData.event_type;
            const deviceType = rawData.device_type || payload.device_type;
            
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
              else if (metric === 'MDC_PRESS_BLD_ART_ABP_SYS') {
                parsedData.BP_SYS = payload.value;
                console.log('[SSE] ✓ MDPNP BP_SYS:', payload.value);
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
              vitals: { HR: parsedData.HR, CO2_ET: parsedData.CO2_ET, BP_SYS: parsedData.BP_SYS, BP_DIA: parsedData.BP_DIA },
              waveformType: parsedData.waveformType,
              waveformLength: parsedData.waveform?.length
            });
            
          } else if (workloadType === '3d-pose') {
            // ✅ Increment counter for every 3D Pose message
            poseMessageCount++;
            
            let allPeopleJoints: any[] = [];
            
            // ✅ Show logs every 30 frames (approximately once per second at 30 FPS)
            if (poseMessageCount % 30 === 0) {
              console.log(`[SSE] 🎯 3D Pose Update (frame ${poseMessageCount}):`, {
                frameNumber: poseMessageCount,
                payload: payload,
                peopleCount: payload.people?.length || 0,
                activity: payload.activity || 'Unknown',
                hasFrameData: !!payload.frame_base64
              });
            }
            
            if (payload.people && Array.isArray(payload.people) && payload.people.length > 0) {
              // ✅ Extract joints from ALL people, not just the first one
              allPeopleJoints = payload.people.map((person: any) => {
                return {
                  person_id: person.person_id,
                  joints_3d: person.joints_3d || [],
                  confidence: person.confidence || [],
                };
              });
              
              // ✅ Show joint extraction logs every 30 frames
              if (poseMessageCount % 30 === 0) {
                console.log('[SSE] ✓ Extracted joints from all people:', {
                  totalPeople: allPeopleJoints.length,
                  jointsPerPerson: allPeopleJoints.map(p => p.joints_3d.length),
                });
              }
            }
            
            parsedData = {
              activity: payload.activity || 'Unknown',
              people: allPeopleJoints,  // ✅ Send all people
              num_persons: payload.people?.length || 0,
              frame_number: payload.frame_number || 0,
            };

            // ✅ Always include frame data immediately (no throttling)
            if (payload.frame_base64) {
              parsedData.frameData = `data:image/jpeg;base64,${payload.frame_base64}`;
              
              // ✅ Show frame logs every 30 frames
              if (poseMessageCount % 30 === 0) {
                console.log(`[SSE] 🎬 Frame received for ${workloadType} (${poseMessageCount} total frames)`);
              }
            }

            // ✅ Show dispatch logs every 30 frames
            if (poseMessageCount % 30 === 0) {
              console.log('[SSE] ✓ Dispatching to Redux:', {
                activity: parsedData.activity,
                peopleCount: parsedData.people.length,
                frameNumber: parsedData.frame_number,
                hasFrameData: !!parsedData.frameData
              });
            }
            
          } else {
            console.warn(`[SSE] ⚠️ Unknown workload type: ${workloadType}`);
          }
          const state: any = store.getState();
          const isProcessing = state.app?.isProcessing;
          if (!isProcessing) {
            console.log('[SSE] ⏸ Ignoring SSE data because app.isProcessing = false', {
              workloadType,
              eventType,
            });
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