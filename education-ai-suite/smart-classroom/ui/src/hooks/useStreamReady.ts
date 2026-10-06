import { useEffect, useRef, useState } from "react";

/**
 * Poll a MediaMTX path until it actually has media on it.
 *
 * MediaMTX's own player is embedded in an iframe, and when it loads before the
 * pipeline has published anything it renders "stream not found" message inside
 * a cross-origin document we cannot restyle. Callers hold the iframe back until
 * this hook reports ready, so the player's first attempt succeeds and the
 * message never appears.
 *
 * Readiness is probed on the same origin as the stream URL, so no extra port or
 * config has to be threaded through the UI:
 *
 *   POST <url>/whep        404 -> "no stream is available on path ..."
 *                          400 -> path has media (our deliberately invalid SDP
 *                                 is only rejected once the stream exists)
 *   GET  <url>/index.m3u8  a body starting #EXTM3U -> path has media
 *
 * Either probe succeeding means ready, which covers both the WebRTC and HLS
 * values of `stream_protocol` without the UI having to know which is in use.
 * MediaMTX sets AllowOrigins '*' on both servers, so the responses are readable
 * cross-origin.
 */

export type StreamReadyState = "waiting" | "ready" | "timeout";

const POLL_INTERVAL_MS = 1000;

/** Give up waiting and show the player anyway, so a failed probe can never
 *  strand the user on a spinner forever. */
const DEFAULT_TIMEOUT_MS = 30000;

async function probeWhep(base: string, signal: AbortSignal): Promise<boolean> {
  const res = await fetch(`${base}/whep`, {
    method: "POST",
    headers: { "Content-Type": "application/sdp" },
    // Deliberately invalid SDP: enough to get past routing, not enough to open
    // a session. A live path answers 400, a missing one answers 404.
    body: "v=0",
    signal,
  });
  return res.status !== 404;
}

async function probeHls(base: string, signal: AbortSignal): Promise<boolean> {
  const res = await fetch(`${base}/index.m3u8`, { method: "GET", signal });
  if (!res.ok) return false;
  // A 200 is not enough. When `base` points at the WebRTC server this path
  // 301-redirects to the player page, and fetch follows it, so an HTML page
  // comes back 200 for every path -- including ones with no stream. Only a
  // real manifest counts.
  return (await res.text()).trimStart().startsWith("#EXTM3U");
}

export function useStreamReady(
  streamUrl: string | undefined,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): StreamReadyState {
  const [state, setState] = useState<StreamReadyState>("waiting");
  const timeoutRef = useRef(timeoutMs);
  timeoutRef.current = timeoutMs;

  useEffect(() => {
    if (!streamUrl) {
      setState("waiting");
      return;
    }

    setState("waiting");

    const base = streamUrl.replace(/\/+$/, "");
    const controller = new AbortController();
    const startedAt = Date.now();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;

      let ready = false;
      try {
        // Both probes race; either one succeeding means there is media.
        const results = await Promise.allSettled([
          probeWhep(base, controller.signal),
          probeHls(base, controller.signal),
        ]);
        ready = results.some((r) => r.status === "fulfilled" && r.value);
      } catch {
        ready = false; // Server not up yet, or a transient refusal mid-startup.
      }

      if (cancelled) return;

      if (ready) {
        setState("ready");
        return;
      }

      if (Date.now() - startedAt >= timeoutRef.current) {
        // Show the player regardless. Its own retry loop takes over from here,
        // which is the behaviour we had before this hook existed.
        setState("timeout");
        return;
      }

      timer = setTimeout(poll, POLL_INTERVAL_MS);
    };

    poll();

    return () => {
      cancelled = true;
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [streamUrl]);

  return state;
}

export default useStreamReady;
