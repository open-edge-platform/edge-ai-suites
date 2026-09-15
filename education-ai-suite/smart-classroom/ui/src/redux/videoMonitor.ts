import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useAppDispatch, useAppSelector } from "../redux/hooks";
import { monitorVideoAnalyticsPipelines } from "../services/api";
import { pipelineLabel } from "../utils/pipelineErrors";
import {
  setVideoStatus,
  setVideoAnalyticsActive,
  setFrontCameraStream,
  setBackCameraStream,
  setBoardCameraStream,
  setActiveStream,
  setHasUploadedVideoFiles,
  setVideoPlaybackMode
} from "../redux/slices/uiSlice";

/** One pipeline's entry in a /monitor-video-analytics-pipeline frame. */
interface PipelineFrame {
  pipeline_name?: string;
  status?: string;
  /** "eos" | "failed" | "stopped" once the backend has called it: the only
   *  signal that this pipeline is not coming back. Null while it is running,
   *  and also in the gap between a crash and the monitor thread's relaunch. */
  final_status?: string | null;
  pid?: number;
  errors?: string[];
}

/** Put a message in the header's notification bar. */
function announce(message: string) {
  window.dispatchEvent(new CustomEvent("global-error", { detail: message }));
}

/** Take a message back down, if it is still the one showing. */
function withdraw(message: string) {
  window.dispatchEvent(
    new CustomEvent("global-error-withdraw", { detail: message })
  );
}

// Clean polls a pipeline must string together before its retry warning comes
// down. One is not enough: a pipeline with a bad source reaches PLAYING and
// errors in the same breath, so a single healthy-looking frame would make the
// message flap on and off every few seconds. At the 2s status cadence this is
// roughly four seconds of actually running.
const HEALTHY_POLLS = 2;

export function useVideoPipelineMonitor() {
  const sessionId = useAppSelector(s => s.ui.sessionId);
  const videoActive = useAppSelector(s => s.ui.videoAnalyticsActive);

  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const abortRef = useRef<AbortController | null>(null);
  const retryTimer = useRef<number | null>(null);
  // Latest t, read at call time — so the effect does not re-subscribe (and tear
  // down its stream) every time the translation function identity changes.
  const tRef = useRef(t);
  tRef.current = t;

  useEffect(() => {
    if (!sessionId || !videoActive) return;
    abortRef.current = new AbortController();

    // Error texts already put in front of the user, keyed "<pipeline>|<text>",
    // so a pipeline repeating the same complaint reports it only once.
    const reported = new Set<string>();
    // Retry warnings currently on the bar, per pipeline. Only these are ever
    // withdrawn — a message about a pipeline that has since given up for good
    // is the verdict on this session and stays until the next one starts.
    const transient = new Map<string, string>();
    // Consecutive clean polls per pipeline, counting towards HEALTHY_POLLS.
    const healthy = new Map<string, number>();
    let announcedAny = false;
    let stopped = false;

    /** A pipeline came back. Drop its warning and let it complain afresh. */
    const clearPipeline = (name: string) => {
      const message = transient.get(name);
      if (message) {
        withdraw(message);
        transient.delete(name);
      }
      for (const key of [...reported]) {
        if (key.startsWith(`${name}|`)) reported.delete(key);
      }
    };

    const startMonitor = async () => {
      try {
        let lastFrame: PipelineFrame[] = [];

        for await (const update of monitorVideoAnalyticsPipelines(
          sessionId,
          abortRef.current!.signal
        )) {
          if (!update?.pipelines) continue;
          const pipelines: PipelineFrame[] = update.pipelines;
          lastFrame = pipelines;

          // Report failures as they happen rather than only at the end. A bad
          // source URL used to fail silently for the whole retry budget — ten
          // relaunches, a minute of nothing on screen — and then surface as a
          // bare "video analytics failed" with no reason attached.
          for (const p of pipelines) {
            const name = p.pipeline_name ?? "";
            const errors = p.errors ?? [];

            if (errors.length > 0) {
              healthy.set(name, 0);
              for (const error of errors) {
                const key = `${name}|${error}`;
                if (reported.has(key)) continue;
                reported.add(key);

                const line = `${pipelineLabel(tRef.current, name)}: ${error}`;
                const retrying = p.final_status == null;
                const message = retrying
                  ? tRef.current("errors.videoPipelineRetrying", { details: line })
                  : tRef.current("errors.videoPipelineFailed", { details: line });

                if (retrying) {
                  transient.set(name, message);
                } else {
                  // Terminal. Supersedes the "retrying" note it replaces, and
                  // is not itself withdrawable.
                  transient.delete(name);
                }
                announce(message);
                announcedAny = true;
              }
              continue;
            }

            // Running clean. The backend drains its error list as it reports,
            // so an absent `errors` really does mean nothing new went wrong.
            if (p.status === "running") {
              const streak = (healthy.get(name) ?? 0) + 1;
              healthy.set(name, streak);
              if (streak >= HEALTHY_POLLS) clearPipeline(name);
            }
          }

          const running = pipelines.filter(p => p.status === "running").length;

          // Settled means every pipeline has a verdict — not merely that none
          // happens to be alive this instant. A crashed pipeline awaiting its
          // relaunch reads as zero running, and calling that a failure was what
          // made a recoverable blip look terminal.
          const anyVerdict = pipelines.some(p => p.final_status != null);
          const allSettled = pipelines.every(
            p => p.final_status != null || p.status === "not_found"
          );

          if (anyVerdict && allSettled) {
            const failed = pipelines.some(p => p.final_status === "failed");
            handleStop(failed ? "failed" : "completed");
            return;
          }

          if (running > 0) dispatch(setVideoStatus("streaming"));
        }

        // The backend closes this stream once everything has settled, so a
        // clean end of iteration is itself a terminal signal.
        if (!stopped) {
          const failed = lastFrame.some(p => p.final_status === "failed");
          handleStop(failed ? "failed" : "completed");
        }
      } catch (err) {
        if (abortRef.current?.signal.aborted) return;
        if (err instanceof Error && err.message.includes("404")) {
          retryTimer.current = window.setTimeout(startMonitor, 1500);
        } else {
          console.warn("Video monitor stopped:", err);
        }
      }
    };

    const handleStop = (status: "failed" | "completed") => {
      if (stopped) return;
      stopped = true;
      console.log("🎥 Pipeline stopped with status:", status);

      dispatch(setVideoStatus(status));
      dispatch(setVideoAnalyticsActive(false));

      if (status === "completed") {
        // It got there in the end. Warnings about blips it recovered from have
        // no business outliving the run they belonged to.
        for (const name of [...transient.keys()]) clearPipeline(name);
        dispatch(setVideoPlaybackMode(true));
        dispatch(setHasUploadedVideoFiles(true));
        console.log("▶ Switching to playback mode");
      }
      if (status === "failed") {
        // It failed without ever saying why.
        if (!announcedAny) {
          announce(tRef.current("notifications.videoAnalyticsFailed"));
        }
        cleanupStreams();
      }
      abortRef.current?.abort();
    };

    const cleanupStreams = () => {
      dispatch(setFrontCameraStream(""));
      dispatch(setBackCameraStream(""));
      dispatch(setBoardCameraStream(""));
      dispatch(setActiveStream(null));
    };

    startMonitor();

    return () => {
      stopped = true;
      // This monitor is going away — and with it anything provisional it is
      // still saying. Otherwise a retry warning outlives the session that
      // raised it and greets the next one from the top of the screen. A
      // terminal failure is not in here, so the verdict survives.
      for (const message of transient.values()) withdraw(message);
      abortRef.current?.abort();
      if (retryTimer.current) {
        clearTimeout(retryTimer.current);
      }
    };
  }, [sessionId, videoActive, dispatch]);
}
