// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import type { SessionSummary } from '../services/api';
import {
  FEATURE_STAGE,
  SETTLED_STAGE_STATUSES,
  STAGE_RUN_AFTER,
  TERMINAL_SESSION_STATES,
} from '../generated/pipeline';

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
 *
 * Stage names, settled statuses and segmentation's prerequisites all come from
 * src/generated/pipeline.ts.
 */

const SEGMENTATION = FEATURE_STAGE.topic_segmentation!;
const REPORT = FEATURE_STAGE.report!;

export type ChainAction = 'segmentation' | 'report' | 'wait' | 'stop';

const isSettled = (status: string | undefined) =>
  !!status && SETTLED_STAGE_STATUSES.includes(status);
const isDeclared = (status: string | undefined) => !!status && status !== 'skipped';

export function decideChainAction(session: SessionSummary): ChainAction {
  if (session.state && TERMINAL_SESSION_STATES.includes(session.state)) return 'stop';

  const stages = session.stages ?? {};
  const segmentation = stages[SEGMENTATION];
  const report = stages[REPORT];

  // Nothing left for this hook to start. Normally fires *before* the session
  // flips to 'completed': the row only settles when the last stage writes its
  // status, which is one request later.
  if (segmentation !== 'pending' && report !== 'pending') return 'stop';

  if (segmentation === 'pending') {
    // Only the prerequisites this session actually declared. A session with no
    // video carries va: 'skipped', and treating that as unfinished would wait
    // forever — the same shape of bug this change exists to fix.
    const unfinished = STAGE_RUN_AFTER[SEGMENTATION].filter(
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
