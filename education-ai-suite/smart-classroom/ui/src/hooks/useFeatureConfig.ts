import { useEffect, useMemo } from 'react';
import { useAppDispatch, useAppSelector } from '../redux/hooks';
import { startLoading, setFeatures, setError, clearError } from '../redux/slices/featureConfigSlice';
import { fetchFeatures, type FeatureDescriptor } from '../services/api';
import { createFeatureGuard } from '../utils/featureGuards';
import { FEATURE_IDS, FEATURE_STAGE } from '../generated/pipeline';

/**
 * How long to wait before trying again after a failed load.
 */
const RETRY_DELAY_MS = 1000;

/**
 * The single in-flight request, shared by every caller.
 */
let inFlight: Promise<FeatureDescriptor[]> | null = null;

const describe = (err: unknown) =>
  (err instanceof Error && err.message) || 'Failed to load features';

/**
 * Compare the live backend's feature graph with the copy this bundle was built
 * from. They only disagree if app and backend are from different builds, which
 * the drift test cannot see. Warn rather than fail: the app still works.
 */
function warnOnCatalogSkew(descriptors: FeatureDescriptor[]): void {
  for (const f of descriptors) {
    if (!FEATURE_IDS.includes(f.id)) {
      console.warn(
        `⚠️ Backend reports feature '${f.id}', which this build does not know. ` +
          'The app and the backend look to be from different versions.',
      );
      continue;
    }
    const expected = FEATURE_STAGE[f.id] ?? null;
    if (f.stage !== undefined && (f.stage ?? null) !== expected) {
      console.warn(
        `⚠️ Feature '${f.id}' owns stage '${f.stage}' on the backend but ` +
          `'${expected}' in this build.`,
      );
    }
  }
}

/**
 * Hook for loading and accessing feature configuration
 */
export function useFeatureConfig() {
  const dispatch = useAppDispatch();
  const { features, loaded, loading, error } = useAppSelector(s => s.featureConfig);

  useEffect(() => {
    if (loaded || loading || error) return;
    // Another caller in this same commit already started it.
    if (inFlight) return;

    dispatch(startLoading());
    inFlight = fetchFeatures();
    inFlight
      .then(descriptors => {
        inFlight = null;
        console.log('✅ Features loaded:', descriptors.map(f => f.id));
        warnOnCatalogSkew(descriptors);
        dispatch(setFeatures(descriptors));
      })
      .catch(err => {
        inFlight = null;
        console.error('❌ Failed to load features:', err);
        dispatch(setError(describe(err)));
      });
  }, [loaded, loading, error, dispatch]);

  // Clearing the error is what re-opens the guard above, so the retry lives on
  // a timer instead of in the effect itself. Every caller arms one, but they
  // collapse: the first clearError to land does the work and the rest are
  // no-ops on an already-null error.
  useEffect(() => {
    if (!error || loaded || loading) return;
    const timer = setTimeout(() => dispatch(clearError()), RETRY_DELAY_MS);
    return () => clearTimeout(timer);
  }, [error, loaded, loading, dispatch]);

  // Memoize the guard to avoid recreating on every render
  const guard = useMemo(() => createFeatureGuard(features), [features]);

  return {
    features,
    guard,
    loaded,
    loading,
    error,
  };
}

/**
 * Hook to check if a specific feature is enabled
 */
export function useHasFeature(featureId: string): boolean {
  const { guard, loaded } = useFeatureConfig();
  return loaded && guard.hasFeature(featureId);
}

/**
 * Hook to get feature endpoint
 */
export function useFeatureEndpoint(featureId: string, endpointKey: string): string | null {
  const { guard, loaded } = useFeatureConfig();
  return loaded ? guard.getEndpoint(featureId, endpointKey) : null;
}
