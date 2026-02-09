import { useEffect } from 'react';
import { useAppDispatch } from './useAppDispatch';
import { setStreamingLock } from '../slices/appSlice';
import { api } from '../../services/api';
import { constants } from '../../constants';

export const useStreamingStatus = (enabled: boolean) => {
  const dispatch = useAppDispatch();

  useEffect(() => {
    if (!enabled) return;

    const pollStatus = async () => {
      try {
        const status = await api.streamingStatus();
        dispatch(setStreamingLock({
          locked: status.locked,
          reason: status.locked ? `Auto-stop in ${status.remaining_seconds}s` : undefined
        }));
      } catch (error) {
        console.error('[StreamingStatus] Poll failed:', error);
      }
    };

    // Poll immediately
    pollStatus();

    // Then poll every 2 seconds
    const interval = setInterval(pollStatus, constants.STREAMING_STATUS_POLL_INTERVAL);

    return () => clearInterval(interval);
  }, [enabled, dispatch]);
};