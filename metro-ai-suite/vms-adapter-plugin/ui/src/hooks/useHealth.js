// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { useState, useEffect, useCallback, useRef } from 'react';
import { getReady } from '@/services/api';

const POLL_INTERVAL_MS = 15_000;

/**
 * Polls GET /v1/ready every 15 seconds.
 * Returns engineStatus: 'connected' | 'degraded' | 'offline' | 'checking'
 */
export function useHealth() {
  const [engineStatus, setEngineStatus] = useState('checking');
  const timerRef = useRef(null);

  const checkHealth = useCallback(async () => {
    try {
      const data = await getReady();
      if (data?.status === 'ready' && (data?.vms_connected ?? false)) {
        setEngineStatus('connected');
      } else if (data?.database) {
        setEngineStatus('degraded');
      } else {
        setEngineStatus('offline');
      }
    } catch {
      setEngineStatus('offline');
    }
  }, []);

  useEffect(() => {
    checkHealth();
    timerRef.current = setInterval(checkHealth, POLL_INTERVAL_MS);
    return () => clearInterval(timerRef.current);
  }, [checkHealth]);

  return engineStatus;
}
