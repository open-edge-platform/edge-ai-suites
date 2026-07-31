import { useEffect, useState } from 'react';

export interface VitalEvent {
  workload_type: string;
  event_type: 'waveform' | 'numeric' | 'pose3d';
  timestamp: number;
  payload: any;
}

export function useSSE(url: string, workloads?: string[]) {
  const [events, setEvents] = useState<VitalEvent[]>([]);
  const [lastEvent, setLastEvent] = useState<VitalEvent | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const queryParams = workloads && workloads.length > 0 
      ? `?workloads=${workloads.join(',')}` 
      : '';
    const eventSourceUrl = `${url}${queryParams}`;

    console.log('[useSSE] Connecting to:', eventSourceUrl);
    
    const eventSource = new EventSource(eventSourceUrl);

    eventSource.onopen = () => {
      console.log('[useSSE] Connected');
      setConnectionStatus('connected');
      setError(null);
    };

    eventSource.onmessage = (event) => {
      if (event.data.startsWith(':')) {
        console.log('[useSSE] Keepalive');
        return;
      }

      try {
        const data: VitalEvent = JSON.parse(event.data);
        console.log('[useSSE] Event:', data.workload_type, data.event_type);
        
        setLastEvent(data);
        setEvents((prev) => [...prev.slice(-99), data]);
      } catch (err) {
        console.error('[useSSE] Parse error:', err);
        setError('Failed to parse event data');
      }
    };

    eventSource.onerror = () => {
      console.error('[useSSE] Connection error');
      setConnectionStatus('disconnected');
      setError('Connection lost. Retrying...');
    };

    return () => {
      console.log('[useSSE] Closing connection');
      eventSource.close();
    };
  }, [url, workloads]);

  return { events, lastEvent, connectionStatus, error };
}