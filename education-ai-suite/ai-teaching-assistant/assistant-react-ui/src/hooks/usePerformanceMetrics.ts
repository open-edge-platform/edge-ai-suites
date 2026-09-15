import { useEffect, useMemo, useRef, useState } from "react";
import {
  getAsrPerformance,
  getPlatformInfo,
  getRagPerformance,
  getSystemMetrics,
  getTtsPerformance,
} from "../api";
import type { PlatformInfo } from "../types";

const POLL_MS = 1500;
const MAX_POINTS = 90;

function keepLast(values: number[], next: number): number[] {
  const updated = [...values, next];
  return updated.length > MAX_POINTS ? updated.slice(updated.length - MAX_POINTS) : updated;
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  return null;
}

export interface HardwareSeries {
  cpu: number[];
  gpu: number[];
  npu: number[];
  memoryPct: number[];
}

export interface ServiceSeries {
  asrMs: number[];
  retrievalMs: number[];
  llmMs: number[];
  ttftMs: number[];
  ttsMs: number[];
}

export interface MetricsState {
  hardware: HardwareSeries;
  services: ServiceSeries;
  current: {
    cpu: number | null;
    gpu: number | null;
    npu: number | null;
    memoryPct: number | null;
    asrMs: number | null;
    retrievalMs: number | null;
    llmMs: number | null;
    ttftMs: number | null;
    ttsMs: number | null;
    tokensPerSec: number | null;
  };
  platform: PlatformInfo | null;
  error: string | null;
}

const INITIAL: MetricsState = {
  hardware: { cpu: [], gpu: [], npu: [], memoryPct: [] },
  services: { asrMs: [], retrievalMs: [], llmMs: [], ttftMs: [], ttsMs: [] },
  current: {
    cpu: null,
    gpu: null,
    npu: null,
    memoryPct: null,
    asrMs: null,
    retrievalMs: null,
    llmMs: null,
    ttftMs: null,
    ttsMs: null,
    tokensPerSec: null,
  },
  platform: null,
  error: null,
};

export function usePerformanceMetrics(paused = false) {
  const [state, setState] = useState<MetricsState>(INITIAL);
  // Read the latest pause flag inside the interval without restarting it.
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      // Skip polling while a response is streaming/playing so metrics traffic
      // doesn't compete with TTS audio delivery to the UI.
      if (pausedRef.current) return;
      const [systemRes, ragRes, ttsRes, asrRes] = await Promise.allSettled([
        getSystemMetrics(),
        getRagPerformance(),
        getTtsPerformance(),
        getAsrPerformance(),
      ]);

      if (cancelled) return;

      setState((prev) => {
        const next: MetricsState = {
          ...prev,
          error: null,
        };

        if (systemRes.status === "fulfilled") {
          const cpuSeries = systemRes.value.cpu_utilization;
          const gpuSeries = systemRes.value.gpu_utilization;
          const npuSeries = systemRes.value.npu_utilization;
          const memSeries = systemRes.value.memory;

          const cpu = cpuSeries.length > 0 ? cpuSeries[cpuSeries.length - 1][1] : null;
          const gpu = gpuSeries.length > 0 ? gpuSeries[gpuSeries.length - 1][1] : null;
          const npu = npuSeries.length > 0 ? npuSeries[npuSeries.length - 1][1] : null;
          const memoryPct = memSeries.length > 0 ? memSeries[memSeries.length - 1][4] : null;

          if (typeof cpu === "number") next.hardware.cpu = keepLast(prev.hardware.cpu, cpu);
          if (typeof gpu === "number") next.hardware.gpu = keepLast(prev.hardware.gpu, gpu);
          if (typeof npu === "number") next.hardware.npu = keepLast(prev.hardware.npu, npu);
          if (typeof memoryPct === "number") {
            next.hardware.memoryPct = keepLast(prev.hardware.memoryPct, memoryPct);
          }

          next.current.cpu = toNumber(cpu);
          next.current.gpu = toNumber(gpu);
          next.current.npu = toNumber(npu);
          next.current.memoryPct = toNumber(memoryPct);
        }

        if (ragRes.status === "fulfilled") {
          const retrievalMs = ragRes.value.latency?.retrieval?.last_ms;
          const llmMs = ragRes.value.latency?.llm?.last_ms;
          const ttftMs = ragRes.value.latency?.llm?.ttft_ms;
          const tps = ragRes.value.latency?.llm?.tokens_per_sec;

          if (typeof retrievalMs === "number") {
            next.services.retrievalMs = keepLast(prev.services.retrievalMs, retrievalMs);
          }
          if (typeof llmMs === "number") next.services.llmMs = keepLast(prev.services.llmMs, llmMs);
          if (typeof ttftMs === "number") next.services.ttftMs = keepLast(prev.services.ttftMs, ttftMs);

          next.current.retrievalMs = toNumber(retrievalMs);
          next.current.llmMs = toNumber(llmMs);
          next.current.ttftMs = toNumber(ttftMs);
          next.current.tokensPerSec = toNumber(tps);
        }

        if (ttsRes.status === "fulfilled") {
          const ttsMs = ttsRes.value.latency?.last_ms;
          if (typeof ttsMs === "number") next.services.ttsMs = keepLast(prev.services.ttsMs, ttsMs);
          next.current.ttsMs = toNumber(ttsMs);
        }

        if (asrRes.status === "fulfilled") {
          const asrMs = asrRes.value.latency?.last_ms;
          if (typeof asrMs === "number") next.services.asrMs = keepLast(prev.services.asrMs, asrMs);
          next.current.asrMs = toNumber(asrMs);
        }

        if (
          systemRes.status === "rejected" &&
          ragRes.status === "rejected" &&
          ttsRes.status === "rejected" &&
          asrRes.status === "rejected"
        ) {
          next.error = "Performance endpoints unavailable";
        }

        return next;
      });
    };

    const loadPlatform = async () => {
      try {
        const info = await getPlatformInfo();
        if (cancelled) return;
        setState((prev) => ({ ...prev, platform: info }));
      } catch {
        if (cancelled) return;
        setState((prev) => ({ ...prev, platform: null }));
      }
    };

    void loadPlatform();
    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, POLL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return useMemo(() => state, [state]);
}
