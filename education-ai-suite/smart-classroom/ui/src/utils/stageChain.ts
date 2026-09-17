// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import type { SessionSummary } from '../services/api';

/**
 * What the stage-driven chain should do next, given one session row.
 *
 * Split out as a pure function on purpose: this is the decision that used to
 * live in useContentSegmentation as a pile of Redux booleans, and the reason it
 * could break silently was that it could not be tested in isolation. Every
 * input here comes from the backend's own stage table, so there is nothing to
 * mock.
 *
 * Note that the table always carries every stage in the vocabulary — the ones
 * this session did not declare are 'skipped' rather than absent (see
 * SessionStore.create). So "declared" is a status test, never a key test.
 */

/** A stage that will not change again on its own. */
const SETTLED = ['done', 'failed', 'interrupted'];

/** States a session cannot move out of — mirrors `_TERMINAL` in session_service.py. */
const TERMINAL_STATES = ['completed', 'failed', 'cancelled'];

/**
 * Everything that has to finish before segmentation can read a complete
 * transcript. `va` is in here because topics are matched against the video
 * timeline, so segmentation must not start while frames are still being
 * analysed.
 */
const SEGMENTATION_PREREQS = ['transcribe', 'summarize', 'mindmap', 'va'];

export type ChainAction = 'segmentation' | 'report' | 'wait' | 'stop';

const isSettled = (status: string | undefined) => !!status && SETTLED.includes(status);
const isDeclared = (status: string | undefined) => !!status && status !== 'skipped';

export function decideChainAction(session: SessionSummary): ChainAction {
  if (session.state && TERMINAL_STATES.includes(session.state)) return 'stop';

  const stages = session.stages ?? {};
  const segmentation = stages.segmentation;
  const report = stages.report;

  // Nothing left for this hook to start. Normally fires *before* the session
  // flips to 'completed': the row only settles when the last stage writes its
  // status, which is one request later.
  if (segmentation !== 'pending' && report !== 'pending') return 'stop';

  if (segmentation === 'pending') {
    // Only the prerequisites this session actually declared. A session with no
    // video carries va: 'skipped', and treating that as unfinished would wait
    // forever — the same shape of bug this change exists to fix.
    const unfinished = SEGMENTATION_PREREQS.filter(
      (stage) => isDeclared(stages[stage]) && !isSettled(stages[stage]),
    );
    return unfinished.length === 0 ? 'segmentation' : 'wait';
  }

  // Deliberately 'settled' and not 'done': a failed segmentation should still
  // let the report be written from whatever did get produced, matching what the
  // report panel already did with contentSegmentationStatus === 'error'.
  if (report === 'pending' && (!isDeclared(segmentation) || isSettled(segmentation))) {
    return 'report';
  }

  return 'wait';
}
