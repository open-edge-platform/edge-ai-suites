// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

/**
 * LiveStreamTab — Live Video Captioning stream viewer.
 *
 * Video: MediaMTX iframe. Requires VITE_MEDIAMTX_BASE to be set to the
 * publicly reachable MediaMTX origin (e.g. http://192.168.1.10:8889).
 * Stream readiness: polls the /whep reverse-proxy until the pipeline
 * starts publishing, then force-reloads the iframe.
 */

import { useState, useEffect, useRef } from 'react';
import { Video, Wifi, WifiOff, StopCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import useLvcStream from '@/hooks/useLvcStream';

// Strip any trailing slash so URL construction is consistent.
// Fall back to window.location.hostname:8889 when the env var is not set at
// build time (e.g. plain `docker compose build` without passing build args),
// preserving the previous behaviour.
const MEDIAMTX_BASE = (import.meta.env.VITE_MEDIAMTX_BASE || '').replace(/\/$/, '');

function mediamtxPlayerUrl(peerId, reloadKey) {
  if (!peerId) return null;
  const base = MEDIAMTX_BASE || `http://${window.location.hostname}:8889`;
  // reloadKey forces a fresh iframe load after pipeline starts publishing
  return `${base}/${peerId}?_k=${reloadKey}`;
}

/** Poll MediaMTX WHEP via the /whep reverse-proxy until stream is publishing (non-404 response). */
async function waitForStream(peerId, signal, intervalMs = 2500) {
  // Use the /whep proxy (vite.config.js in dev, nginx.conf in prod) — avoids
  // hard-coded hostnames and mixed-content issues on HTTPS deployments.
  const whepUrl = `/whep/${peerId}/whep`;
  while (!signal.aborted) {
    try {
      const resp = await fetch(whepUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/sdp' },
        body: 'v=0\r\n',
        signal,
      });
      // 404 = no one publishing yet; anything else (400 bad SDP, 405, …) = stream exists
      if (resp.status !== 404) return true;
    } catch { /* network / abort */ }
    if (signal.aborted) break;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return false;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatStreamSeconds(seconds) {
  const mins = Math.floor(seconds / 60);
  const remaining = seconds - mins * 60;
  return `${String(mins).padStart(2, '0')}:${remaining.toFixed(2).padStart(5, '0')}`;
}

function captionPositionLabel(index) {
  return index === 0 ? 'Latest' : `Latest -${index}`;
}

function captionTimestampLabel(entry) {
  if (entry.timestampSeconds != null) return formatStreamSeconds(entry.timestampSeconds);
  return new Date().toLocaleTimeString();
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function LiveStreamTab({ lvcRuns = [], onStopLvc }) {
  const [stopped,    setStopped]    = useState(false);
  const [streamReady, setStreamReady] = useState(false);
  const [reloadKey,  setReloadKey]  = useState(0);
  const abortRef = useRef(null);

  // Use the first active run
  const activeRun = lvcRuns[0] ?? null;

  // captionHistory from run (set at start time) or local override
  const [captionHistoryOverride, setCaptionHistoryOverride] = useState(null);
  const captionHistory = captionHistoryOverride ?? activeRun?.captionHistory ?? 3;

  const { captions, connected: sseConnected } = useLvcStream(lvcRuns.length > 0);
  const runCaptions = activeRun ? (captions[activeRun.runId] ?? []).slice(0, captionHistory) : [];

  // Reset stopped state and captionHistory override when a new run becomes active
  useEffect(() => {
    setStopped(false);
    setCaptionHistoryOverride(null);
  }, [activeRun?.runId]);

  // When run changes, poll MediaMTX until stream is publishing then reload iframe
  useEffect(() => {
    const peerId = activeRun?.peerId;
    if (!peerId) {
      setStreamReady(false);
      return;
    }

    // Abort any prior polling
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    setStreamReady(false);

    waitForStream(peerId, ac.signal).then((ready) => {
      if (ready && !ac.signal.aborted) {
        setStreamReady(true);
        setReloadKey((k) => k + 1); // force iframe src change → fresh load
      }
    });

    return () => ac.abort();
  }, [activeRun?.peerId]);

  const playerUrl = mediamtxPlayerUrl(activeRun?.peerId, reloadKey);

  const handleStop = async () => {
    if (!activeRun) return;
    abortRef.current?.abort();
    setStopped(true);
    try {
      await onStopLvc(activeRun.runId || activeRun.run_id);
    } catch {
      setStopped(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 max-w-[480px]">
      {/* ── Run info bar ── */}
      {activeRun && (
        <div className="flex items-center justify-between px-3 py-1.5 bg-[#EBF5FF] rounded border border-[#C3DCF5]">
          <div className="flex items-center gap-2 text-[0.72rem]">
            <span className="font-semibold text-[#0E1C47]">Run:</span>
            <span className="font-mono text-[#0071C5] truncate max-w-[120px]">{activeRun.runId}</span>
            <span className="vms-badge vms-badge-green text-[0.62rem]">{activeRun.status ?? 'running'}</span>
            <span className="flex items-center gap-1 text-[#6B7BA4]">
              {sseConnected
                ? <><Wifi size={10} className="text-[#0DBF8C]" /> live</>
                : <><WifiOff size={10} className="text-[#A3B0CC]" /> off</>}
            </span>
          </div>
          <Button
            size="sm"
            variant="destructive"
            className="h-6 text-[0.68rem] px-2"
            onClick={handleStop}
            disabled={stopped}
          >
            <StopCircle size={11} className="mr-1" />Stop
          </Button>
        </div>
      )}

      {/* ── Video player (MediaMTX iframe) ── */}
      <div className="relative bg-black rounded overflow-hidden w-full aspect-video flex items-center justify-center" style={{ maxHeight: '240px' }}>
        {!activeRun && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white/40">
            <Video size={32} strokeWidth={1.2} />
            <p className="text-[0.72rem]">Configure and click "Start Analysis" to begin</p>
          </div>
        )}
        {/* Waiting overlay — shown while pipeline is starting up */}
        {activeRun && !streamReady && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-black/80">
            <Loader2 size={24} className="animate-spin text-white/70" />
            <p className="text-[0.72rem] text-white/60 animate-pulse">Starting pipeline…</p>
          </div>
        )}
        {activeRun && playerUrl && (
          <iframe
            key={`${activeRun.peerId}-${reloadKey}`}
            src={playerUrl}
            allow="autoplay"
            className="w-full h-full border-0"
            title="Live Video Stream"
          />
        )}
      </div>

      {/* ── Caption ticker ── */}
      {activeRun && (
        <div className="vms-surface p-2 flex flex-col gap-1.5 max-h-[140px] overflow-y-auto">
          <div className="flex items-center justify-between">
            <p className="text-[0.62rem] font-bold uppercase tracking-[0.6px] text-[#6B7BA4]">Live Captions</p>
          </div>
          {runCaptions.length === 0 ? (
            <p className="text-[0.72rem] italic text-[#A3B0CC]">Waiting for captions…</p>
          ) : (
            runCaptions.map((entry, i) => (
              <div key={i} className={`flex flex-col px-2 py-0.5 rounded ${
                i === 0 ? 'bg-[#EBF5FF] text-[#0E1C47]' : 'text-[#4A5C80]'
              }`}>
                <span className="text-[0.62rem] text-[#6B7BA4] font-mono leading-none mb-0.5">
                  {captionPositionLabel(i)} • {captionTimestampLabel(entry)}
                </span>
                <span className={`text-[0.75rem] leading-snug ${i === 0 ? 'font-medium' : ''}`}>
                  {entry.text}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
