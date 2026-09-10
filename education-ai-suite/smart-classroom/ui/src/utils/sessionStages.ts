import type { FeatureGuard } from './featureGuards';
import type { SessionStage } from '../services/api';

/**
 * What a session intends to run, given its inputs and the enabled features.
 *
 * This is the contract behind the session history: the backend marks a session
 * completed once every declared stage settles, so the list has to be exactly
 * the stages that will run on their own. Declare one that needs a click the
 * user may never make and the session stays open forever; leave one out and the
 * session is called finished while work is still going.
 *
 * The chain being mirrored lives in useAudioPipeline (transcript -> summary ->
 * mind map) and useContentSegmentation (-> segmentation -> report). Its first
 * condition is that audio exists, which is why a video-only session declares
 * nothing but video analytics.
 *
 * Both entry points - Start recording and Upload files - call this so they
 * cannot drift apart.
 */
export function declaredStages(
  guard: FeatureGuard,
  inputs: { hasAudio: boolean; hasVideo: boolean },
): SessionStage[] {
  const stages: SessionStage[] = [];

  if (inputs.hasAudio) {
    if (guard.hasFeature('asr')) stages.push('transcribe');
    if (guard.hasFeature('summary')) stages.push('summarize');
    if (guard.hasFeature('mindmap')) stages.push('mindmap');
    // Segmentation follows the mind map automatically, and its success in turn
    // auto-starts the report. With video in the mix segmentation also waits on
    // the user opening playback mode - still declared, because a session where
    // that never happens genuinely did not finish.
    if (guard.hasFeature('topic_segmentation')) stages.push('segmentation');
    if (guard.hasFeature('report')) stages.push('report');
  }

  if (inputs.hasVideo && guard.hasFeature('video_analytics')) stages.push('va');

  return stages;
}
