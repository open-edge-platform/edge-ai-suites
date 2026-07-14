import { useEffect, useRef } from 'react';
import { useDispatch } from 'react-redux';
import { updateDetectionState } from '../slices/detectionSlice';
import { mockDetectionState, generateLiveMockState } from '../../lib/mockData';
import type { DetectionState } from '../../types/detection';
import type { AppDispatch } from '../store';

export function useDetectionMockStream(intervalMs = 1000) {
  const dispatch = useDispatch<AppDispatch>();
  const stateRef = useRef<DetectionState>(mockDetectionState);

  useEffect(() => {
    const timer = setInterval(() => {
      stateRef.current = generateLiveMockState(stateRef.current);
      dispatch(updateDetectionState(stateRef.current));
    }, intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs, dispatch]);
}