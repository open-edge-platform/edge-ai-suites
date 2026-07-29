import { useEffect, useRef } from 'react';
import { useDispatch } from 'react-redux';
import { updateNicuState } from '../slices/nicuSlice';
import { mockNicuState, generateLiveMockState } from '../../lib/mockData';
import type { NicuState } from '../../types/nicu';
import type { AppDispatch } from '../store';

export function useNicuMockStream(intervalMs = 1000) {
  const dispatch = useDispatch<AppDispatch>();
  const stateRef = useRef<NicuState>(mockNicuState);

  useEffect(() => {
    const timer = setInterval(() => {
      stateRef.current = generateLiveMockState(stateRef.current);
      dispatch(updateNicuState(stateRef.current));
    }, intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs, dispatch]);
}