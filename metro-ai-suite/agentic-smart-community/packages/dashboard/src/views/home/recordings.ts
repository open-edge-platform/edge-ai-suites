// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
import type { RecordingSegment } from "./type";

export interface CoverageBlock {
  key: string;
  startMs: number;
  endMs: number;
}

// Continuous recording writes one segment per minute, so a full day is ~1440
// rows. Merge them into the handful of uninterrupted spans they actually form
// before rendering — one DOM node per row would be unusable.
export const mergeCoverage = (
  segments: RecordingSegment[],
  gapToleranceMs = 5000,
): CoverageBlock[] => {
  const ordered = [...segments].sort((a, b) => a.startMs - b.startMs);
  const blocks: CoverageBlock[] = [];

  ordered.forEach((segment) => {
    const previous = blocks[blocks.length - 1];

    if (previous && segment.startMs - previous.endMs <= gapToleranceMs) {
      previous.endMs = Math.max(previous.endMs, segment.endMs);
      return;
    }

    blocks.push({
      key: `coverage-${segment.id}`,
      startMs: segment.startMs,
      endMs: segment.endMs,
    });
  });

  return blocks;
};

export const findRecordingAt = (
  segments: RecordingSegment[],
  timeMs: number,
): RecordingSegment | null => {
  return (
    segments.find(
      (segment) => timeMs >= segment.startMs && timeMs < segment.endMs,
    ) || null
  );
};

export const findNextRecording = (
  segments: RecordingSegment[],
  afterStartMs: number,
): RecordingSegment | null => {
  return (
    [...segments]
      .sort((a, b) => a.startMs - b.startMs)
      .find((segment) => segment.startMs > afterStartMs) || null
  );
};
