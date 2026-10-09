import { useEffect, useRef } from 'react';
import { useAppSelector } from './hooks';
import { beaconAbortSession } from '../services/api';

/**
 * Tells the backend the page went away mid-run, so the session history does not
 * keep showing it as running.
 *
 * The app drives its stages one HTTP request at a time, so nothing on the
 * server notices a browser that simply closes. The backend derives completion
 * from the stages, which covers a session that finished; this covers the one
 * that did not.
 *
 * `pagehide` rather than `visibilitychange`: hidden fires on an ordinary tab
 * switch, which happens constantly during a recording and must not abort it.
 * `pagehide` also survives bfcache, where the old `unload` event does not.
 *
 * No filtering on whether the session already finished — /finalize refuses to
 * overwrite a session that reached a terminal state, so a late beacon is a
 * no-op and the decision stays on the side that actually knows.
 */
export function useSessionAbortBeacon() {
  const sessionId = useAppSelector((s) => s.ui.sessionId);

  // Read at unload time, so it must be a ref: re-binding the listener on every
  // session change would be pointless churn.
  const sessionRef = useRef<string | null>(null);
  sessionRef.current = sessionId ?? null;

  useEffect(() => {
    const onPageHide = (e: PageTransitionEvent) => {
      // persisted means the page went into bfcache and may yet come back with
      // its state intact — the run is not over.
      if (e.persisted) return;
      const id = sessionRef.current;
      if (id) beaconAbortSession(id);
    };

    window.addEventListener('pagehide', onPageHide);
    return () => window.removeEventListener('pagehide', onPageHide);
  }, []);
}
