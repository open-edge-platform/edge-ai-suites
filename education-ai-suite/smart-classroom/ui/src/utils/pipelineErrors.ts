/**
 * Helpers for reading failures out of the video-analytics endpoints.
 *
 * Both `/start-video-analytics-pipeline` and `/stop-video-analytics-pipeline`
 * answer HTTP 200 even when every pipeline fails: the reason only lives in 
 * each result's `error` field.
 */

/** One entry per pipeline in a start/stop video-analytics response. */
export interface PipelineResult {
  status?: string;
  pipeline_name?: string;
  error?: string;
  stream_url?: string;
}

/** Minimal shape of i18next's `t`, so callers can pass theirs unchanged. */
type Translate = (key: string, options?: Record<string, unknown>) => string;

// Backend pipeline id → i18n key for the camera name shown to the user.
const CAMERA_LABEL_KEYS: Record<string, string> = {
  front: 'cameras.front',
  back: 'cameras.back',
  content: 'cameras.board',
};

export function pipelineLabel(t: Translate, pipelineName?: string): string {
  const key = pipelineName ? CAMERA_LABEL_KEYS[pipelineName] : undefined;
  return key ? t(key) : pipelineName || '';
}

/**
 * Reasons the failed pipelines give, one "<camera>: <reason>" line each.
 * `skip` filters out failures that are expected rather than actionable.
 */
export function collectPipelineErrors(
  results: PipelineResult[] | undefined,
  t: Translate,
  fallback: string,
  skip?: (result: PipelineResult) => boolean
): string[] {
  if (!Array.isArray(results)) return [];
  return results
    .filter((r) => r.status === 'error' && !skip?.(r))
    .map((r) => `${pipelineLabel(t, r.pipeline_name)}: ${r.error || fallback}`);
}

/**
 * A stop request for a pipeline that was never running. The UI asks to stop
 * whatever it believes is streaming, so a stale entry is normal housekeeping,
 * not something to put in front of the user.
 */
export function isNotRunning(result: PipelineResult): boolean {
  return /is not running/i.test(result.error || '');
}
