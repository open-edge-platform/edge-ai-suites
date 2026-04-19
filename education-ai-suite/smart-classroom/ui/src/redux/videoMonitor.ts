import { useEffect, useRef } from "react";
import { useAppDispatch, useAppSelector } from "../redux/hooks";
import { monitorVideoAnalyticsPipelines } from "../services/api";
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

export function useVideoPipelineMonitor() {
  const sessionId = useAppSelector(s => s.ui.sessionId);
  const videoActive = useAppSelector(s => s.ui.videoAnalyticsActive);
  const videoLoading = useAppSelector(s => s.ui.videoAnalyticsLoading);

  const dispatch = useAppDispatch();
  const abortRef = useRef<AbortController | null>(null);
  const retryTimer = useRef<number | null>(null);

  useEffect(() => {
    if (!sessionId || !videoActive) return;
    abortRef.current = new AbortController();

    const startMonitor = async () => {
      try {
        for await (const update of monitorVideoAnalyticsPipelines(
          sessionId,
          abortRef.current!.signal
        )) {
          if (!update?.pipelines) continue;

          let running = 0;

          for (const p of update.pipelines) {
            if (p.status === "running") running++;
            // Log transient errors but don't fail — the backend restarts automatically.
            if (p.errors && p.errors.length > 0) {
              console.warn(
                `⚠️ Pipeline '${p.pipeline_name}' (PID ${p.pid}) reported errors: ${p.errors.join(", ")}. Waiting for restart...`
              );
            }
          }

          // Only stop monitoring when no pipelines are running at all.
          // A single pipeline exiting and restarting will keep running > 0.
          if (running === 0) {
            const hasErrors = update.pipelines.some(
              (p: any) =>
                p.status === "stopped_error" ||
                (p.errors && p.errors.length > 0)
            );
            handleStop(hasErrors ? "failed" : "completed");
            return;
          }

          dispatch(setVideoStatus("streaming"));
        }
      } catch (err: any) {
        if (err.message?.includes("404")) {
          retryTimer.current = window.setTimeout(startMonitor, 1500);
        } else {
          console.warn("Video monitor stopped:", err);
        }
      }
    };

    const handleStop = (status: "failed" | "completed") => {
      console.log("🎥 Pipeline stopped with status:", status);

      dispatch(setVideoStatus(status));
      dispatch(setVideoAnalyticsActive(false));

      if (status === "completed") {
        dispatch(setVideoPlaybackMode(true));
        dispatch(setHasUploadedVideoFiles(true));
        console.log("▶ Switching to playback mode");
      }
      if (status === "failed") {
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
      abortRef.current?.abort();
      if (retryTimer.current) {
        clearTimeout(retryTimer.current);
      }
    };
  }, [sessionId, videoActive]);
}
