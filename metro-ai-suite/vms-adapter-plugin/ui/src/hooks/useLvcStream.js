// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

/**
 * useLvcStream — subscribes to the Live Captioning SSE metadata stream.
 *
 * Returns a `captions` map keyed by runId, where each value is an array of
 * caption objects { text, timestampSeconds } (most-recent first).
 *
 * Usage:
 *   const { captions, connected } = useLvcStream(enabled);
 *   const myCaptions = captions[runId] ?? [];
 */

import { useEffect, useRef, useState } from 'react';

const SSE_URL = '/v1/analytics-apps/live_captioning/results/stream';

export default function useLvcStream(enabled = false) {
  const [captions, setCaptions] = useState({});   // { [runId]: {text, timestampSeconds}[] }
  const [connected, setConnected] = useState(false);
  const esRef = useRef(null);

  useEffect(() => {
    if (!enabled) {
      esRef.current?.close();
      esRef.current = null;
      setConnected(false);
      return;
    }

    const es = new EventSource(SSE_URL);
    esRef.current = es;

    es.onopen = () => setConnected(true);

    es.onmessage = (ev) => {
      try {
        const envelope = JSON.parse(ev.data);
        // Skip heartbeats — only handle caption envelopes
        if (envelope?.type === 'status' || envelope?.type === 'heartbeat' || !envelope?.runId) return;

        const data = envelope.data ?? {};
        const text =
          data.text ||
          data.caption ||
          data.result ||
          data.objects?.[0]?.meta?.label ||
          (typeof data === 'string' ? data : null);

        if (text) {
          const entry = {
            text,
            timestampSeconds: data.timestamp_seconds ?? null,
          };
          setCaptions((prev) => {
            const existing = prev[envelope.runId] ?? [];
            return { ...prev, [envelope.runId]: [entry, ...existing].slice(0, 20) };
          });
        }
      } catch {
        // non-JSON keep-alive comment — ignore
      }
    };

    es.onerror = () => setConnected(false);

    return () => {
      es.close();
      esRef.current = null;
      setConnected(false);
    };
  }, [enabled]);

  return { captions, connected };
}
