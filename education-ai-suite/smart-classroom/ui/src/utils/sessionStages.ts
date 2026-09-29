import type { FeatureGuard } from './featureGuards';
import {
  FEATURES_BY_INPUT,
  FEATURE_STAGE,
  STAGE_ORDER,
  type PipelineInput,
  type SessionStage,
} from '../generated/pipeline';

/**
 * What a session intends to run, given its inputs and the enabled features.
 *
 * This is the contract behind the session history: the backend marks a session
 * completed once every declared stage settles, so the list has to be exactly
 * the stages that will run on their own. Declare one that needs a click the
 * user may never make and the session stays open forever; leave one out and the
 * session is called finished while work is still going.
 *
 * The feature -> stage mapping and each stage's input come from
 * src/generated/pipeline.ts, the same table the backend runs the chain off.
 *
 * The chain being mirrored lives in useAudioPipeline (transcript -> summary ->
 * mind map) and useStageDrivenChain (-> segmentation -> report). The latter
 * starts segmentation and the report off this very table, so declaring them is
 * self-fulfilling — which is the point: the previous trigger lived in Redux and
 * could stall silently, leaving the session on 'running' for good.
 *
 * Both entry points - Start recording and Upload files - call this so they
 * cannot drift apart.
 */
export function declaredStages(
  guard: FeatureGuard,
  inputs: { hasAudio: boolean; hasVideo: boolean },
): SessionStage[] {
  const present: Record<PipelineInput, boolean> = {
    audio: inputs.hasAudio,
    video: inputs.hasVideo,
  };

  const declared = new Set<SessionStage>();
  for (const input of Object.keys(present) as PipelineInput[]) {
    if (!present[input]) continue;
    for (const id of FEATURES_BY_INPUT[input]) {
      const stage = FEATURE_STAGE[id];
      if (stage && guard.hasFeature(id)) declared.add(stage);
    }
  }

  return STAGE_ORDER.filter((stage) => declared.has(stage));
}
