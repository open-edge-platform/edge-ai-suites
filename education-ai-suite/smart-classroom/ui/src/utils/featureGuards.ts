import type { FeatureDescriptor } from '../redux/slices/featureConfigSlice';
import {
  FEATURES_BY_INPUT,
  FEATURES_BY_SCREEN,
  type FeatureScreen,
  type PipelineInput,
} from '../generated/pipeline';

/**
 * Feature Guard - Centralized feature availability and configuration access
 */
export class FeatureGuard {
  private featureMap: Map<string, FeatureDescriptor>;

  constructor(features: FeatureDescriptor[]) {
    this.featureMap = new Map(features.map(f => [f.id, f]));
  }

  /**
   * Check if a feature is enabled
   */
  hasFeature(id: string): boolean {
    return this.featureMap.has(id);
  }

  /**
   * Get a specific feature descriptor
   */
  getFeature(id: string): FeatureDescriptor | undefined {
    return this.featureMap.get(id);
  }

  /**
   * Get endpoint URL for a feature
   */
  getEndpoint(featureId: string, endpointKey: string): string | null {
    const feature = this.featureMap.get(featureId);
    return feature?.endpoints?.[endpointKey] || null;
  }

  /**
   * Get all endpoints for a feature
   */
  getEndpoints(featureId: string): Record<string, string> | null {
    const feature = this.featureMap.get(featureId);
    return feature?.endpoints || null;
  }

  /**
   * Get summary mode (dialog, teacher, hybrid)
   */
  getSummaryMode(): string {
    const summary = this.featureMap.get('summary');
    return summary?.mode || 'dialog';
  }

  /**
   * Whether ASR streams partial transcripts. When false, an uploaded file is
   * transcribed in a single pass and nothing shows up until it completes.
   */
  isAsrChunkingEnabled(): boolean {
    return this.featureMap.get('asr')?.chunking !== false;
  }

  /**
   * Whether speaker diarization is enabled in the ASR model config.
   */
  isDiarizationEnabled(): boolean {
    return this.featureMap.get('asr')?.diarization === true;
  }

  /**
   * Get list of all enabled feature IDs
   */
  getEnabledFeatures(): string[] {
    return Array.from(this.featureMap.keys());
  }

  /**
   * Check if multiple features are all enabled
   */
  hasAllFeatures(...featureIds: string[]): boolean {
    return featureIds.every(id => this.hasFeature(id));
  }

  /**
   * Check if at least one feature is enabled
   */
  hasAnyFeature(...featureIds: string[]): boolean {
    return featureIds.some(id => this.hasFeature(id));
  }

  /**
   * Whether anything is enabled that works from a given source. Membership
   * comes from the generated catalog, not from a list at the call site.
   */
  hasAnyFeatureForInput(input: PipelineInput): boolean {
    return FEATURES_BY_INPUT[input].some(id => this.hasFeature(id));
  }

  /**
   * Whether anything belonging to a screen is enabled. Drives the app's
   * auto-switch when the main features are all off.
   */
  hasAnyFeatureForScreen(screen: FeatureScreen): boolean {
    return FEATURES_BY_SCREEN[screen].some(id => this.hasFeature(id));
  }

  /**
   * Get feature dependencies
   */
  getDependencies(featureId: string): string[] {
    const feature = this.featureMap.get(featureId);
    return feature?.dependency || [];
  }

  /**
   * Get feature capabilities required
   */
  getRequires(featureId: string): string[] {
    const feature = this.featureMap.get(featureId);
    return feature?.requires || [];
  }
}

/**
 * React hook-friendly feature guard creator
 */
export function createFeatureGuard(features: FeatureDescriptor[]): FeatureGuard {
  return new FeatureGuard(features);
}
