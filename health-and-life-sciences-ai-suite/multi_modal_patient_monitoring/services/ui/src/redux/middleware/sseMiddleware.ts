import type { Middleware } from '@reduxjs/toolkit';
import { addEvent } from '../slices/eventsSlice';
import { 
  updateWorkloadData, 
  setAggregatorStatus 
} from '../slices/servicesSlice';
import type { RootState } from '../store';

export const sseMiddleware: Middleware = (store) => {
  let eventSource: EventSource | null = null;

  return (next) => (action) => {
    // Type guard to check if action has required properties
    if (typeof action !== 'object' || action === null || !('type' in action)) {
      return next(action);
    }

    // Handle SSE connect action
    if (action.type === 'sse/connect') {
      const url = (action as any).payload?.url;
      
      if (!url) {
        console.error('[SSE] No URL provided in connect action');
        return next(action);
      }

      console.log('[SSE] Connecting to:', url);

      // Close existing connection
      if (eventSource) {
        eventSource.close();
      }

      // Create new connection
      eventSource = new EventSource(url);
      store.dispatch(setAggregatorStatus('connecting'));

      eventSource.onopen = () => {
        console.log('[SSE] Connected');
        store.dispatch(setAggregatorStatus('connected'));
      };

      eventSource.onmessage = (event) => {
        // Skip keepalive messages
        if (event.data.startsWith(':')) {
          return;
        }

        try {
          const data = JSON.parse(event.data);
          
          console.log('[SSE] Received event:', data);

          // Dispatch to events slice
          const eventObj = {
            id: `${data.workload || 'unknown'}-${Date.now()}`,
            workload: data.workload || 'unknown',
            timestamp: Date.now(),
            data: data,
          };
          
          store.dispatch(addEvent(eventObj));

          // Update workload data in services slice
          if (data.workload) {
            store.dispatch(
              updateWorkloadData({
                workloadId: data.workload,
                data: data.vitals || data.data || {},
              })
            );
          }
        } catch (err) {
          console.error('[SSE] Failed to parse event data:', err);
        }
      };

      eventSource.onerror = (error) => {
        console.error('[SSE] Connection error:', error);
        store.dispatch(setAggregatorStatus('error'));
        
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
      };
    }

    // Handle SSE disconnect action
    if (action.type === 'sse/disconnect') {
      console.log('[SSE] Disconnecting');
      
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      
      store.dispatch(setAggregatorStatus('disconnected'));
    }

    return next(action);
  };
};