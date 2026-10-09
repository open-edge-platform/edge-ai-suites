// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef } from 'react';
import { useAppDispatch, useAppSelector } from './hooks';
import {
  startContentSegmentation,
  contentSegmentationSuccess,
  contentSegmentationFailed,
  startReport,
} from './slices/uiSlice';
import { generateContentSegmentation, getSessionStatus } from '../services/api';
import { decideChainAction } from '../utils/stageChain';
import type { FeatureGuard } from '../utils/featureGuards';

const POLL_MS = 2500;

/** Consecutive request failures tolerated before giving up on the session. */
const MAX_ERRORS = 3;

/**
 * Starts segmentation, and then the report, off the backend's stage table.
 *
 * Both used to be triggered from Redux — whether a File object was still in
 * the store, whether a metadata upload had succeeded, whether the video had
 * reached playback mode. Every one of those was a way for the chain to stall
 * with nothing logged: a microphone session never satisfied the audio test at
 * all, and an audio+video session lost its trigger the moment the video files
 * were cleared. The session then sat on 'running' until the tab closed.
 *
 * The stage table has none of those problems. It is written by the same
 * stage_tracker that runs the work, it survives a reload, and it says plainly
 * which stages this session declared. Polling it is a little less immediate
 * than watching local state, and that is the whole cost.
 *
 * The browser still drives the chain, so closing the page still stops it. What
 * changes is that an open page now always gets there.
 */
export function useStageDrivenChain(featureGuard: FeatureGuard) {
  const dispatch = useAppDispatch();
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const sessionRegistered = useAppSelector((s) => s.ui.sessionRegistered);

  // Guards against a second trigger while the first request is in flight: a
  // tick can land before the backend has moved the stage off 'pending'.
  const inFlight = useRef<Set<string>>(new Set());

  const relevant =
    featureGuard.hasFeature('topic_segmentation') || featureGuard.hasFeature('report');

  useEffect(() => {
    if (!sessionId || !sessionRegistered || !relevant) return;

    let cancelled = false;
    let timer: number | null = null;
    let errors = 0;

    const stop = () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
    };

    const runSegmentation = async () => {
      const key = `${sessionId}:segmentation`;
      if (inFlight.current.has(key)) return;
      inFlight.current.add(key);
      dispatch(startContentSegmentation());
      try {
        await generateContentSegmentation(sessionId);
        dispatch(contentSegmentationSuccess());
      } catch (e: unknown) {
        // The stage row already carries the failure, and the next tick reads it
        // and moves on to the report. This only mirrors it into the UI.
        dispatch(
          contentSegmentationFailed(e instanceof Error ? e.message : String(e)),
        );
      } finally {
        inFlight.current.delete(key);
      }
    };

    // Self-rescheduling rather than setInterval: a slow status response must
    // not let ticks pile up on top of each other.
    const tick = async () => {
      if (cancelled) return;

      let session;
      try {
        session = await getSessionStatus(sessionId);
        errors = 0;
      } catch (e) {
        errors += 1;
        if (errors >= MAX_ERRORS) {
          console.warn(
            `⚠️ Stage chain giving up on ${sessionId} after ${errors} failed status checks`,
            e,
          );
          return stop();
        }
        timer = window.setTimeout(tick, POLL_MS);
        return;
      }

      if (cancelled) return;

      // No row: never registered, or deleted from the history panel. Either way
      // there is nothing left to read.
      if (session === null) {
        console.warn(`⚠️ Stage chain stopping: no session row for ${sessionId}`);
        return stop();
      }

      switch (decideChainAction(session)) {
        case 'stop':
          return stop();
        case 'segmentation':
          void runSegmentation();
          break;
        case 'report': {
          // The report panel owns generation; this only asks for it, exactly as
          // the old segmentation-success handler did. Asked once and never
          // cleared: the stage takes a moment to leave 'pending', and repeating
          // the request meanwhile would keep resetting the panel's status.
          // Regenerating afterwards is the panel's own button, not this hook's.
          const key = `${sessionId}:report`;
          if (!inFlight.current.has(key)) {
            inFlight.current.add(key);
            dispatch(startReport());
          }
          break;
        }
        case 'wait':
          break;
      }

      timer = window.setTimeout(tick, POLL_MS);
    };

    void tick();
    return stop;
  }, [sessionId, sessionRegistered, relevant, dispatch]);
}
