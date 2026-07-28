import { useEffect, useMemo } from 'react';
import { useAppDispatch, useAppSelector } from '../redux/hooks';
import { startLoading, setFeatures, setError } from '../redux/slices/featureConfigSlice';
import { fetchFeatures, type FeatureDescriptor } from '../services/api';
import { createFeatureGuard, FeatureGuard } from '../utils/featureGuards';

/**
 * Hook for loading and accessing feature configuration
 */
export function useFeatureConfig() {
  const dispatch = useAppDispatch();
  const { features, loaded, loading, error } = useAppSelector(s => s.featureConfig);

  useEffect(() => {
    if (loaded || loading) return;

    dispatch(startLoading());
    fetchFeatures()
      .then(descriptors => {
        console.log('✅ Features loaded:', descriptors.map(f => f.id));
        dispatch(setFeatures(descriptors));
      })
      .catch(err => {
        console.error('❌ Failed to load features:', err);
        dispatch(setError(err.message || 'Failed to load features'));
      });
  }, [loaded, loading, dispatch]);

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

/**
 * Hook to get camera configuration
 */
export function useCameraConfig() {
  const { guard, loaded } = useFeatureConfig();
  return loaded ? guard.getCameraConfig() : { front: false, back: false, board: false };
}
