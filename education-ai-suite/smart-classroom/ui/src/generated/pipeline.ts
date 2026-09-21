// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// GENERATED FILE - do not edit.
// Written by Scripts/gen_catalog.py from utils/pipeline_catalog.py. Edit there and re-run it.

/** Every feature the backend can expose. */
export type FeatureId = 'asr' | 'summary' | 'mindmap' | 'topic_segmentation' | 'video_analytics' | 'board_ocr' | 'content_search' | 'qa' | 'grading' | 'report';

/** The pipeline stages the session API knows about. */
export type SessionStage = 'transcribe' | 'summarize' | 'mindmap' | 'va' | 'segmentation' | 'report';

/** The source a stage needs to be worth declaring. */
export type PipelineInput = 'audio' | 'video';

/** The screen a feature belongs to, for the app's auto-switch. */
export type FeatureScreen = 'content_search' | 'grading' | 'main';

export const FEATURE_IDS: readonly FeatureId[] = ['asr', 'summary', 'mindmap', 'topic_segmentation', 'video_analytics', 'board_ocr', 'content_search', 'qa', 'grading', 'report'];

/**
 * Stage order, as the backend runs them. A session's table always carries every
 * one; the stages it did not declare are 'skipped' rather than absent.
 */
export const STAGE_ORDER: readonly SessionStage[] = ['transcribe', 'summarize', 'mindmap', 'va', 'segmentation', 'report'];

/** The stage each feature owns. Features without one are absent. */
export const FEATURE_STAGE: Readonly<Partial<Record<FeatureId, SessionStage>>> = {
  asr: 'transcribe',
  summary: 'summarize',
  mindmap: 'mindmap',
  topic_segmentation: 'segmentation',
  video_analytics: 'va',
  report: 'report',
};

/** The feature that owns each stage. */
export const STAGE_FEATURE: Readonly<Record<SessionStage, FeatureId>> = {
  transcribe: 'asr',
  summarize: 'summary',
  mindmap: 'mindmap',
  segmentation: 'topic_segmentation',
  va: 'video_analytics',
  report: 'report',
};

/**
 * What has to have FINISHED before a stage may start. A different graph from
 * `dependsOn`, which is what has to be ENABLED.
 */
export const STAGE_RUN_AFTER: Readonly<Record<SessionStage, readonly SessionStage[]>> = {
  transcribe: [],
  summarize: ['transcribe'],
  mindmap: ['summarize'],
  segmentation: ['transcribe', 'summarize', 'mindmap', 'va'],
  va: [],
  report: ['segmentation'],
};

/** The input a stage needs before a session should declare it. */
export const STAGE_INPUT: Readonly<Record<SessionStage, PipelineInput>> = {
  transcribe: 'audio',
  summarize: 'audio',
  mindmap: 'audio',
  segmentation: 'audio',
  va: 'video',
  report: 'audio',
};

/** Features grouped by the input they work from. */
export const FEATURES_BY_INPUT: Readonly<Record<PipelineInput, readonly FeatureId[]>> = {
  audio: ['asr', 'summary', 'mindmap', 'topic_segmentation', 'report'],
  video: ['video_analytics'],
};

/** Features grouped by the screen they belong to. */
export const FEATURES_BY_SCREEN: Readonly<Record<FeatureScreen, readonly FeatureId[]>> = {
  main: ['asr', 'summary', 'mindmap', 'topic_segmentation', 'video_analytics', 'report'],
  content_search: ['content_search', 'qa'],
  grading: ['grading'],
};

/** Every value a stage's status can take. */
export const STAGE_STATUSES: readonly string[] = ['pending', 'running', 'done', 'failed', 'interrupted', 'skipped'];

/** A stage that will not change again on its own. */
export const SETTLED_STAGE_STATUSES: readonly string[] = ['done', 'failed', 'interrupted'];

export const SESSION_STATES: readonly string[] = ['pending', 'running', 'completed', 'failed', 'cancelled'];

/** States a session cannot move out of. */
export const TERMINAL_SESSION_STATES: readonly string[] = ['completed', 'failed', 'cancelled'];
