// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// GENERATED FILE - do not edit.
// Written by Scripts/gen_catalog.py from utils/pipeline_catalog.py. Edit there and re-run it.

// Every feature, in settings-screen toggle order. `dependsOn` is what must be
// ENABLED; features/resolver.py auto-enables it at startup.
const FEATURES = {
  asr: { label: 'Speech recognition', dependsOn: [], stage: 'transcribe', input: 'audio', screen: 'main' },
  summary: { label: 'Summary', dependsOn: ['asr'], stage: 'summarize', input: 'audio', screen: 'main' },
  mindmap: { label: 'Mind map', dependsOn: ['summary'], stage: 'mindmap', input: 'audio', screen: 'main' },
  topic_segmentation: { label: 'Topic segmentation', dependsOn: ['asr', 'content_search'], stage: 'segmentation', input: 'audio', screen: 'main' },
  video_analytics: { label: 'Video analytics', dependsOn: [], stage: 'va', input: 'video', screen: 'main' },
  board_ocr: { label: 'Board OCR', dependsOn: ['video_analytics'], stage: null, input: null, screen: null },
  content_search: { label: 'Content search', dependsOn: [], stage: null, input: null, screen: 'content_search' },
  qa: { label: 'Question answering', dependsOn: ['content_search'], stage: null, input: null, screen: 'content_search' },
  grading: { label: 'Grading', dependsOn: [], stage: null, input: null, screen: 'grading' },
  report: { label: 'Report', dependsOn: ['summary', 'mindmap', 'topic_segmentation', 'video_analytics'], stage: 'report', input: 'audio', screen: 'main' },
};

// Feature id -> every feature whose presence drags it in, however deep.
const REQUIRED_BY = {
  asr: ['summary', 'mindmap', 'topic_segmentation', 'report'],
  summary: ['mindmap', 'report'],
  mindmap: ['report'],
  topic_segmentation: ['report'],
  video_analytics: ['board_ocr', 'report'],
  board_ocr: [],
  content_search: ['topic_segmentation', 'qa', 'report'],
  qa: [],
  grading: [],
  report: [],
};

// Every pipeline stage, in run order.
const STAGE_ORDER = ['transcribe', 'summarize', 'mindmap', 'va', 'segmentation', 'report'];

module.exports = { FEATURES, REQUIRED_BY, STAGE_ORDER };
